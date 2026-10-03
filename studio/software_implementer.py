"""Bounded implementation engine for Satoshi Studio Software Assembler.

Consumes a planner run, asks a software-engineering model for complete-file edits
restricted to planner-approved paths, validates those edits, writes them only in
the current git worktree, and lets GitHub Actions run tests before any PR update.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import openai_runtime

ROOT = Path(__file__).resolve().parents[1]
MAX_FILE_BYTES = 220_000
MAX_TOTAL_CONTEXT = 600_000
PROTECTED = {
    ".github/workflows/satoshi-software-assembler.yml",
    "studio/software_assembler.py",
    "studio/software_implementer.py",
}
FORBIDDEN_PREFIXES = (
    ".git/",
    ".github/secrets/",
    "node_modules/",
    ".venv/",
    "venv/",
)


def run(cmd: list[str], timeout: int = 300) -> tuple[int, str]:
    proc = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)
    return proc.returncode, proc.stdout[-30_000:]


def clean_path(value: str) -> str:
    value = value.strip().replace("\\", "/")
    if not value or value.startswith("/") or ".." in Path(value).parts:
        raise ValueError(f"Unsafe path: {value!r}")
    if any(value.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
        raise ValueError(f"Forbidden path: {value}")
    return value


def read_context(paths: list[str]) -> list[dict]:
    result, used = [], 0
    for raw in paths:
        path = clean_path(raw)
        target = ROOT / path
        if target.exists() and target.is_file():
            size = target.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError(f"Planner-approved file too large for bounded implementation: {path}")
            text = target.read_text(errors="replace")
        else:
            text = ""
        used += len(text)
        if used > MAX_TOTAL_CONTEXT:
            raise ValueError("Implementation context exceeds bounded limit")
        result.append({"path": path, "exists": target.exists(), "content": text})
    return result


def edit_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "edits", "tests"],
        "properties": {
            "summary": {"type": "string"},
            "edits": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["path", "content", "reason"],
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                },
            },
            "tests": {"type": "array", "items": {"type": "string"}},
        },
    }


def propose(step: dict, objective: str, context: list[dict], failure: str = "",
            model: str | None = None) -> dict:
    model = model or os.environ.get("SATOSHI_ASSEMBLER_MODEL", "gpt-5.6-sol")
    instructions = """You are the bounded implementation engineer for Satoshi Studio.
Implement exactly one approved engineering-plan step. You may edit only paths
provided in allowed_paths. Return complete UTF-8 file contents, never diffs.
Preserve existing architecture unless the step explicitly changes it. Reuse
canonical Studio modules and shared runtimes. Do not bypass tests, approval gates,
media-spend gates, scientific-integrity checks, provider live gates, or publication
approval. Never add plaintext credentials. Never claim a test passed; Actions will
run tests after your edits. Prefer the smallest maintainable change. If a prior
test failure is supplied, repair its root cause without broadening scope."""
    body = {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": json.dumps({
            "objective": objective,
            "step": step,
            "allowed_paths": [x["path"] for x in context],
            "files": context,
            "prior_test_failure": failure,
        }, ensure_ascii=False),
        "reasoning": {"effort": "high"},
        "max_output_tokens": 20_000,
        "text": {"format": {"type": "json_schema", "name": "assembler_edits",
                              "strict": True, "schema": edit_schema()}},
    }
    response = openai_runtime.call_responses(body, timeout=300, max_bytes=8_000_000)
    payload, _ = openai_runtime.extract_json(response)
    return payload


def validate_and_apply(payload: dict, allowed: set[str]) -> list[str]:
    touched = []
    seen = set()
    for edit in payload.get("edits", []):
        path = clean_path(edit["path"])
        if path not in allowed:
            raise ValueError(f"Model attempted unapproved path: {path}")
        if path in PROTECTED:
            raise ValueError(f"Self-modification is prohibited during implementation: {path}")
        if path in seen:
            raise ValueError(f"Duplicate edit for {path}")
        seen.add(path)
        content = edit["content"]
        if not isinstance(content, str) or len(content.encode()) > MAX_FILE_BYTES:
            raise ValueError(f"Invalid/oversized replacement for {path}")
        if re.search(r"(?:sk-[A-Za-z0-9_-]{20,}|RUNWAYML_API_SECRET\s*=\s*[\"'][^$])", content):
            raise ValueError(f"Possible plaintext credential in {path}")
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        touched.append(path)
    if not touched:
        raise ValueError("Implementation model returned no edits")
    return touched


def targeted_checks(paths: list[str]) -> list[list[str]]:
    checks = []
    if any(p.endswith(".py") for p in paths):
        checks.append(["python", "-m", "py_compile", *[p for p in paths if p.endswith(".py")]])
    if any(p.startswith("remotion/") and p.endswith((".ts", ".tsx")) for p in paths):
        checks.append(["npm", "run", "typecheck"])
    return checks


def implement(run_dir: Path, max_steps: int, max_repairs: int) -> dict:
    plan_path = run_dir / "plan.json"
    if not plan_path.exists():
        raise ValueError(f"Missing plan: {plan_path}")
    plan = json.loads(plan_path.read_text())
    objective = plan["objective"]
    report = {"objective": objective, "steps": [], "status": "running"}
    for step in sorted(plan["implementation_plan"], key=lambda x: x["order"])[:max_steps]:
        allowed_paths = [clean_path(p) for p in step.get("paths", [])]
        if not allowed_paths:
            report["steps"].append({"order": step["order"], "status": "skipped", "reason": "no paths"})
            continue
        if any(path in PROTECTED for path in allowed_paths):
            report["steps"].append({"order": step["order"], "status": "blocked", "reason": "protected assembler path"})
            report["status"] = "blocked"
            break
        base_contents = {x["path"]: x["content"] for x in read_context(allowed_paths)}
        failure = ""
        success = False
        for attempt in range(max_repairs + 1):
            context = read_context(allowed_paths)
            payload = propose(step, objective, context, failure=failure)
            touched = validate_and_apply(payload, set(allowed_paths))
            failures = []
            for cmd in targeted_checks(touched):
                check_cmd = cmd
                cwd_cmd = check_cmd
                if cmd[:3] == ["npm", "run", "typecheck"]:
                    code, output = run(["bash", "-lc", "cd remotion && npm run typecheck"], timeout=240)
                else:
                    code, output = run(cmd, timeout=240)
                if code:
                    failures.append(output)
            if not failures:
                success = True
                report["steps"].append({
                    "order": step["order"], "status": "implemented", "attempt": attempt + 1,
                    "summary": payload.get("summary", ""), "paths": touched,
                })
                break
            failure = "\n\n".join(failures)[-30_000:]
            for path, original in base_contents.items():
                target = ROOT / path
                if original == "" and not target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(original)
        if not success:
            for path, original in base_contents.items():
                target = ROOT / path
                if original == "" and target.exists():
                    target.unlink()
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(original)
            report["steps"].append({"order": step["order"], "status": "failed", "failure": failure})
            report["status"] = "failed"
            break
    else:
        report["status"] = "implemented"
    (run_dir / "implementation_report.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--max-steps", type=int, default=4)
    parser.add_argument("--max-repairs", type=int, default=1)
    args = parser.parse_args()
    if not (1 <= args.max_steps <= 8):
        raise SystemExit("max-steps must be 1..8")
    if not (0 <= args.max_repairs <= 2):
        raise SystemExit("max-repairs must be 0..2")
    report = implement(ROOT / args.run_dir, args.max_steps, args.max_repairs)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "implemented" else 2


if __name__ == "__main__":
    raise SystemExit(main())
