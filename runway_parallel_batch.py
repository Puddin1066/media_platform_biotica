"""Submit a frozen Satoshi Runway asset manifest in parallel.

This intentionally bypasses the research/supervisor/maintenance loop. The input
manifest is the creative contract. Every paid task is schema-validated through
runway_operation.py, the total first-pass estimate must fit under the manifest
credit ceiling and current account balance, and automatic retries are forbidden.

Usage:
  python runway_parallel_batch.py --manifest production_specs/tetris_runway_parallel.json
  python runway_parallel_batch.py --manifest ... --live
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import runway_operation


def _request_id(job: dict[str, Any]) -> str:
    payload = json.dumps(job, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def compile_request(job: dict[str, Any]) -> dict[str, Any]:
    required = {"id", "kind", "purpose", "operation", "model", "estimated_credits", "body"}
    if set(job) != required:
        raise ValueError(f"Job {job.get('id', '<unknown>')} must contain exactly {sorted(required)}")
    credits = job["estimated_credits"]
    if not isinstance(credits, (int, float)) or credits <= 0:
        raise ValueError(f"Job {job['id']} needs a positive credit estimate")
    body = dict(job["body"])
    if body.get("model") != job["model"]:
        raise ValueError(f"Job {job['id']} model mismatch")
    request = {
        "operation": job["operation"],
        "request_id": _request_id(job),
        "allow_mutation": True,
        "allow_media_spend": True,
        "estimated_credits": credits,
        "body": body,
    }
    runway_operation.validate(request)
    return request


def load_manifest(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported manifest schema")
    jobs = data.get("jobs")
    if not isinstance(jobs, list) or not jobs:
        raise ValueError("Manifest needs at least one job")
    ids = [job.get("id") for job in jobs]
    if len(ids) != len(set(ids)):
        raise ValueError("Job IDs must be unique")
    cap = data.get("max_credits")
    if not isinstance(cap, (int, float)) or cap <= 0:
        raise ValueError("Manifest max_credits must be positive")
    estimated = sum(float(job.get("estimated_credits", 0)) for job in jobs)
    declared = data.get("first_pass_estimated_credits")
    if declared is not None and abs(float(declared) - estimated) > 1e-9:
        raise ValueError(f"Declared first-pass credits {declared} != computed {estimated:g}")
    if estimated > cap:
        raise ValueError(f"First pass {estimated:g} exceeds hard manifest cap {cap:g}")
    for job in jobs:
        compile_request(job)
    return data


def _execute_one(job: dict[str, Any], root: Path) -> dict[str, Any]:
    request = compile_request(job)
    result = runway_operation.execute(
        request,
        checkpoint=lambda: None,
        job_root=root / "jobs",
        work_root=root / "work",
    )
    return {
        "job_id": job["id"],
        "purpose": job["purpose"],
        "kind": job["kind"],
        "model": job["model"],
        "estimated_credits": job["estimated_credits"],
        "request_id": request["request_id"],
        "result": result,
    }


def run(manifest_path: str | Path, output: str | Path, live: bool = False,
        max_workers: int = 8) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    jobs = manifest["jobs"]
    estimate = sum(float(job["estimated_credits"]) for job in jobs)

    plan = {
        "status": "validated",
        "episode": manifest.get("episode"),
        "max_credits": manifest["max_credits"],
        "first_pass_estimated_credits": estimate,
        "parallel_jobs": len(jobs),
        "jobs": [
            {
                "id": job["id"],
                "purpose": job["purpose"],
                "operation": job["operation"],
                "model": job["model"],
                "estimated_credits": job["estimated_credits"],
                "request_id": _request_id(job),
                "prompt": job["body"].get("promptText", ""),
            }
            for job in jobs
        ],
    }
    (output / "plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    if not live:
        return plan
    if os.environ.get("RUNWAY_LIVE_ENABLED") != "true":
        raise ValueError("RUNWAY_LIVE_ENABLED=true is required for --live")
    if not os.environ.get("RUNWAYML_API_SECRET"):
        raise ValueError("RUNWAYML_API_SECRET is required for --live")

    organization = runway_operation.api("GET", "/v1/organization")
    balance = organization.get("creditBalance")
    if not isinstance(balance, (int, float)):
        raise ValueError("Runway did not return a numeric credit balance")
    if balance < estimate:
        raise ValueError(f"Runway balance {balance:g} is below first-pass estimate {estimate:g}")

    results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    workers = max(1, min(int(max_workers), len(jobs), 8))

    # All requests are independent by design. No creative agent is allowed to
    # rewrite prompts between submission and collection.
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(_execute_one, job, output): job for job in jobs}
        for future in concurrent.futures.as_completed(future_map):
            job = future_map[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({
                    "job_id": job["id"],
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:3000],
                })

    results.sort(key=lambda row: row["job_id"])
    failures.sort(key=lambda row: row["job_id"])
    record = {
        "status": "completed" if not failures else "partial_failure",
        "episode": manifest.get("episode"),
        "submitted_in_parallel": True,
        "first_pass_estimated_credits": estimate,
        "starting_credit_balance": balance,
        "results": results,
        "failures": failures,
        "automatic_retry": False,
    }
    (output / "results.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if failures:
        raise RuntimeError(f"{len(failures)} Runway batch jobs failed; inspect {output / 'results.json'}")
    return record


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--output", default="outputs/runway-parallel")
    p.add_argument("--max-workers", type=int, default=8)
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    try:
        result = run(args.manifest, args.output, args.live, args.max_workers)
        print(json.dumps(result, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError, TypeError) as exc:
        p.exit(1, f"Runway parallel batch blocked: {exc}\n")


if __name__ == "__main__":
    main()
