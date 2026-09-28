"""Bounded OpenAI code-repair agent for the Satoshi media pipeline.

Reads the current supervisor state, most recent failure log, and an allowlisted set
of source files. Produces complete-file replacements only inside that allowlist.
It never touches workflows, secrets, publishing code, budgets, or general tests.
A single provider-contract test file may be synchronized when a mocked provider
call is stale relative to the installed SDK contract; safety/publication/evidence
tests remain outside the agent's authority.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path

MODEL = os.environ.get("SATOSHI_MAINTENANCE_MODEL", "gpt-5.6-sol")
ENDPOINT = "https://api.openai.com/v1/responses"
ALLOWLIST = [
    "positioning.py",
    "satoshi_short.py",
    "satoshi_supervisor.py",
    "unreviewed_video_preview.py",
    "episode.py",
    "runway_media.py",
    "provider_readiness.py",
    "remotion/src/root.tsx",
    "test_production.py",
]
FORBIDDEN_SNIPPETS = [
    "secrets.",
    "GITHUB_TOKEN",
    "META_ACCESS_TOKEN",
    "IG_USER_ID",
    "publish it",
    "git push --force",
]
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["diagnosis", "patches", "confidence", "requires_human"],
    "properties": {
        "diagnosis": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "requires_human": {"type": "boolean"},
        "patches": {
            "type": "array",
            "maxItems": 3,
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
    },
}


def read_text(path: str, limit: int = 70000) -> str:
    p = Path(path)
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")[:limit]


def context_payload() -> dict:
    return {
        "target": "Produce an unreviewed preview until remotion/out/reel.mp4 exists.",
        "policy": {
            "allowed_files": ALLOWLIST,
            "provider_contract_test_exception": (
                "test_production.py may be changed only to synchronize mocked provider-call arguments/endpoints "
                "with the installed provider SDK when the production repair and test otherwise conflict. Do not "
                "remove assertions, weaken safety/review/rights checks, or alter unrelated tests."
            ),
            "forbidden": [
                "Do not change GitHub workflow files, secrets, credentials, budgets, publishing code, or account configuration.",
                "Do not change any test file except test_production.py, and only for narrow provider SDK contract synchronization.",
                "Do not weaken evidence provenance, review gates, rights checks, publication controls, or safety checks merely to make a test pass.",
                "Prefer the smallest deterministic repair. Reuse cached provider/media state rather than regenerate paid work.",
                "Return no patch if the failure requires credentials, an external account change, or human editorial judgment.",
            ],
        },
        "supervisor_state": read_text("outputs/supervisor/state.json", 20000),
        "failure_log": read_text("/tmp/satoshi-supervisor.log", 30000),
        "request": read_text("requests/satoshi/current.json", 12000),
        "files": {path: read_text(path) for path in ALLOWLIST},
    }


def call_agent(payload: dict) -> dict:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    body = {
        "model": MODEL,
        "store": False,
        "reasoning": {"effort": "high"},
        "instructions": (
            "You are a senior production-maintenance engineer. Diagnose the first blocking failure in a bounded media pipeline. "
            "Patch only files explicitly allowlisted in the input. Preserve evidence, review, budget and publication safety boundaries. "
            "Prefer deterministic replay/resume fixes over new provider calls. Return complete replacement file content, not diffs. "
            "You may synchronize test_production.py only when a mocked provider contract is stale relative to the installed SDK; "
            "never weaken unrelated assertions or safety controls. If a safe repair is not possible from the supplied context, "
            "set requires_human=true and return patches=[]."
        ),
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 22000,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "maintenance_repair",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as response:
        result = json.loads(response.read().decode("utf-8"))
    if result.get("status") != "completed":
        raise RuntimeError("Maintenance agent response did not complete")
    texts = []
    for item in result.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
    if not texts:
        raise RuntimeError("Maintenance agent returned no structured output")
    return json.loads("".join(texts))


def validate_and_apply(result: dict, dry_run: bool = False) -> list[str]:
    patches = result.get("patches") or []
    if result.get("requires_human"):
        return []
    if not patches:
        raise RuntimeError("Agent proposed no repair and did not request human intervention")
    changed = []
    for patch in patches:
        path = patch.get("path")
        content = patch.get("content")
        if path not in ALLOWLIST:
            raise RuntimeError("Agent attempted non-allowlisted path: " + repr(path))
        if not isinstance(content, str) or not content.strip() or len(content) > 120000:
            raise RuntimeError("Agent returned invalid replacement content for " + path)
        lowered = content.lower()
        for snippet in FORBIDDEN_SNIPPETS:
            if snippet.lower() in lowered:
                raise RuntimeError("Agent output contains forbidden capability in " + path)
        if path == "test_production.py":
            old = read_text(path, 120000)
            if "test_generated_visual_is_a_reviewable_illustration" not in old or \
                    "test_generated_visual_is_a_reviewable_illustration" not in content:
                raise RuntimeError("Provider-contract test synchronization cannot remove the visual provider test")
            if content.count("def test_") < old.count("def test_"):
                raise RuntimeError("Provider-contract test synchronization cannot remove tests")
        if not dry_run:
            Path(path).write_text(content, encoding="utf-8")
        changed.append(path)
    return changed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default="outputs/supervisor/maintenance-agent.json")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = call_agent(context_payload())
    changed = validate_and_apply(result, dry_run=args.dry_run)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({**result, "changed_files": changed}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"requires_human": result.get("requires_human"), "changed_files": changed, "diagnosis": result.get("diagnosis")}, indent=2))
    if result.get("requires_human"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
