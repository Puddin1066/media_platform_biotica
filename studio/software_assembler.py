"""Satoshi Studio objective-driven software assembler.

This agent is intentionally plan-first. It crawls the repository, builds a compact
architecture inventory, asks a software-engineering model to infer the minimum
pipeline changes needed for an objective, and emits machine-readable artifacts.
Code mutation remains a reviewed PR step; the planner never writes arbitrary
model-generated code directly to main.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

import openai_runtime

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "studio" / "assembler" / "runs"
TEXT_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yml", ".yaml", ".md"}
IGNORE_DIRS = {".git", "node_modules", ".next", "dist", "build", "coverage", "__pycache__", ".venv", "venv"}
PRIORITY_PREFIXES = (
    ".github/workflows/",
    "studio/",
    "remotion/",
    "tests/",
    "fixtures/",
)
MAX_FILE_BYTES = 180_000
MAX_EXCERPT_CHARS = 6_000
MAX_FILES = 220


def sha(value) -> str:
    raw = value if isinstance(value, str) else json.dumps(value, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def safe_read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return ""
        return path.read_text(errors="replace")
    except OSError:
        return ""


def classify(path: str) -> str:
    if path.startswith(".github/workflows/"):
        return "workflow"
    if path.startswith("studio/"):
        return "studio"
    if path.startswith("remotion/"):
        return "renderer"
    if path.startswith(("tests/", "fixtures/")) or path.startswith("test_"):
        return "test"
    if path.endswith(".md"):
        return "docs"
    return "runtime"


def dependencies(path: str, text: str) -> list[str]:
    deps = set()
    if path.endswith(".py"):
        for match in re.findall(r"^(?:from|import)\s+([A-Za-z0-9_\.]+)", text, re.M):
            deps.add(match.split(".")[0])
    elif path.endswith((".js", ".jsx", ".ts", ".tsx")):
        for match in re.findall(r"(?:from\s+|require\()[\'\"]([^\'\"]+)", text):
            deps.add(match)
    elif path.endswith((".yml", ".yaml")):
        for match in re.findall(r"(?:uses:|workflow:)\s*([^\s#]+)", text):
            deps.add(match)
    return sorted(deps)[:60]


def entrypoint_signals(path: str, text: str) -> list[str]:
    signals = []
    probes = {
        "workflow_dispatch": "manual workflow",
        "schedule:": "scheduled workflow",
        "pull_request:": "PR workflow",
        "push:": "push workflow",
        "def main(": "CLI/runtime entrypoint",
        "if __name__ == \"__main__\"": "python executable",
        "module_runner": "Studio module runner",
        "assembly_manifest": "assembly contract",
        "distribution.json": "publish contract",
        "OPENAI_LIVE_ENABLED": "live OpenAI gate",
        "RUNWAY_LIVE_ENABLED": "live Runway gate",
    }
    for needle, label in probes.items():
        if needle in text:
            signals.append(label)
    return signals


def crawl(root: Path = ROOT) -> dict:
    files = []
    candidates = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        priority = 0 if rel.startswith(PRIORITY_PREFIXES) else 1
        candidates.append((priority, rel, path))
    candidates.sort(key=lambda item: (item[0], item[1]))
    for _, rel, path in candidates[:MAX_FILES]:
        text = safe_read(path)
        if not text:
            continue
        files.append({
            "path": rel,
            "kind": classify(rel),
            "bytes": len(text.encode(errors="ignore")),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "dependencies": dependencies(rel, text),
            "signals": entrypoint_signals(rel, text),
            "excerpt": text[:MAX_EXCERPT_CHARS],
        })
    modules_path = root / "studio" / "modules.json"
    modules = json.loads(modules_path.read_text()) if modules_path.exists() else {"modules": []}
    workflows = [f for f in files if f["kind"] == "workflow"]
    studio_files = [f for f in files if f["kind"] == "studio"]
    return {
        "schema_version": 1,
        "repository": "Puddin1066/media_platform_biotica",
        "root_sha256": sha([(f["path"], f["sha256"]) for f in files]),
        "summary": {
            "files_scanned": len(files),
            "workflow_count": len(workflows),
            "studio_file_count": len(studio_files),
            "module_count": len(modules.get("modules", [])),
        },
        "modules": modules.get("modules", []),
        "files": files,
    }


def schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["objective", "current_state", "endpoint_contract", "gaps", "implementation_plan", "verification", "maintenance", "risk_controls"],
        "properties": {
            "objective": {"type": "string"},
            "current_state": {"type": "array", "items": {"type": "string"}},
            "endpoint_contract": {
                "type": "object",
                "additionalProperties": False,
                "required": ["input", "output", "success_criteria"],
                "properties": {
                    "input": {"type": "string"},
                    "output": {"type": "string"},
                    "success_criteria": {"type": "array", "items": {"type": "string"}},
                },
            },
            "gaps": {"type": "array", "items": {"type": "string"}},
            "implementation_plan": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["order", "change", "paths", "reason", "tests"],
                    "properties": {
                        "order": {"type": "integer"},
                        "change": {"type": "string"},
                        "paths": {"type": "array", "items": {"type": "string"}},
                        "reason": {"type": "string"},
                        "tests": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
            "verification": {"type": "array", "items": {"type": "string"}},
            "maintenance": {"type": "array", "items": {"type": "string"}},
            "risk_controls": {"type": "array", "items": {"type": "string"}},
        },
    }


def plan(objective: str, inventory: dict, model: str | None = None, reasoning: str = "high") -> dict:
    model = model or os.environ.get("SATOSHI_ASSEMBLER_MODEL", "gpt-5.6-sol")
    instructions = """You are the senior software assembler for Satoshi Studio.
Treat the repository as an evolving production system, not a greenfield project.
Infer architecture from the supplied inventory. Optimize for the user's endpoint,
then for maintainability, observability, resumability, cost control, and least
privilege. Reuse current Studio modules and shared runtimes before adding another
pipeline. Identify stale/legacy paths but never delete or mutate them unless the
objective requires it. Prefer one canonical pipeline and explicit contracts.
Do not invent files, secrets, provider capabilities, or successful tests. Every
implementation step must name paths already present or clearly mark new paths.
Return an engineering plan, not prose commentary."""
    payload = json.dumps({"objective": objective, "inventory": inventory}, ensure_ascii=False)
    body = {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": payload,
        "reasoning": {"effort": reasoning},
        "max_output_tokens": 7000,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "satoshi_software_assembler_plan",
                "strict": True,
                "schema": schema(),
            }
        },
    }
    result = openai_runtime.call_responses(body, timeout=240)
    planned, _ = openai_runtime.extract_json(result)
    planned["planner"] = {"model": result.get("model", model), "reasoning": reasoning}
    planned["inventory_sha256"] = inventory["root_sha256"]
    return planned


def render_markdown(planned: dict) -> str:
    lines = ["# Satoshi Studio Software Assembler Plan", "", f"**Objective:** {planned['objective']}", ""]
    lines += ["## Endpoint contract", "", f"**Input:** {planned['endpoint_contract']['input']}", "", f"**Output:** {planned['endpoint_contract']['output']}", ""]
    lines += ["### Success criteria"] + [f"- {x}" for x in planned["endpoint_contract"]["success_criteria"]] + [""]
    for heading, key in [("Current state", "current_state"), ("Gaps", "gaps")]:
        lines += [f"## {heading}", ""] + [f"- {x}" for x in planned[key]] + [""]
    lines += ["## Implementation plan", ""]
    for step in sorted(planned["implementation_plan"], key=lambda x: x["order"]):
        lines += [f"### {step['order']}. {step['change']}", "", step["reason"], "", "Paths:"]
        lines += [f"- `{x}`" for x in step["paths"]]
        lines += ["", "Tests:"] + [f"- {x}" for x in step["tests"]] + [""]
    for heading, key in [("Verification", "verification"), ("Maintenance", "maintenance"), ("Risk controls", "risk_controls")]:
        lines += [f"## {heading}", ""] + [f"- {x}" for x in planned[key]] + [""]
    return "\n".join(lines)


def write_run(objective: str, inventory: dict, planned: dict | None = None) -> Path:
    run_id = os.environ.get("GITHUB_RUN_ID") or sha(objective + inventory["root_sha256"])[:12]
    out = OUT / str(run_id)
    out.mkdir(parents=True, exist_ok=True)
    (out / "architecture_inventory.json").write_text(json.dumps(inventory, indent=2, ensure_ascii=False) + "\n")
    (out / "objective.txt").write_text(objective.strip() + "\n")
    if planned:
        (out / "plan.json").write_text(json.dumps(planned, indent=2, ensure_ascii=False) + "\n")
        (out / "PLAN.md").write_text(render_markdown(planned) + "\n")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["inventory", "plan"])
    parser.add_argument("--objective", default="")
    parser.add_argument("--objective-file")
    parser.add_argument("--model")
    parser.add_argument("--reasoning", default="high", choices=["low", "medium", "high"])
    args = parser.parse_args()
    objective = args.objective
    if args.objective_file:
        objective = Path(args.objective_file).read_text().strip()
    inventory = crawl()
    if args.command == "inventory":
        out = write_run(objective or "Repository architecture inventory", inventory)
        print(out)
        return 0
    if not objective.strip():
        raise SystemExit("--objective or --objective-file is required for plan")
    planned = plan(objective.strip(), inventory, model=args.model, reasoning=args.reasoning)
    out = write_run(objective.strip(), inventory, planned)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
