"""Topic-driven Satoshi short orchestration.

Preview mode is fully automatic: topic -> research case -> OpenAI web-search draft
-> engagement validation -> review package. Media production remains downstream
of the existing reviewed-claim handoff.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

import narrative_mode
import produce
import short_format
import positioning
import topic_case

def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path

def prepare(topic, angle, output, live=False, budget=0, max_usd_per_run=0,
            model=None, max_tool_calls=6):
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    case = topic_case.build(topic, angle)
    case_path = _write(root / "topic-case.json", case)
    plan = produce.default_plan(case)
    _write(root / "research-plan.json", plan)
    model = model or os.environ.get("OPENAI_CREATIVE_MODEL",
              os.environ.get("OPENAI_PRODUCE_MODEL",
              os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")))

    explicit_mode = os.environ.get("SATOSHI_NARRATIVE_MODE", "")
    selected_mode = narrative_mode.choose_mode(topic, angle, case, explicit_mode)
    source_family = narrative_mode.source_family_for_mode(selected_mode)
    prior_mode = os.environ.get("SATOSHI_NARRATIVE_MODE")
    os.environ["SATOSHI_NARRATIVE_MODE"] = selected_mode
    try:
        result = produce.run(case, plan, "short", model, root / "produce",
                             live=live, budget=budget, max_usd_per_run=max_usd_per_run,
                             max_tool_calls=max_tool_calls)
    finally:
        if prior_mode is None:
            os.environ.pop("SATOSHI_NARRATIVE_MODE", None)
        else:
            os.environ["SATOSHI_NARRATIVE_MODE"] = prior_mode

    manifest = {
        "topic": topic, "angle": angle, "case": str(case_path),
        "mode": "live_research" if live else "dry_run",
        "narrative_mode": selected_mode,
        "source_family": source_family,
        "produce": result, "status": result["status"], "publishable": False
    }
    if live:
        draft_dir = Path(result["path"])
        draft = json.loads((draft_dir / "draft.json").read_text(encoding="utf-8"))
        cited_urls = [s["url"] for s in draft["sources"] if s.get("role") == "cited"]
        position_validation = positioning.validate(draft["script"]["positioning"], cited_urls)
        validation = short_format.validate_script(draft["script"])
        _write(root / "positioning.json", draft["script"]["positioning"])
        _write(root / "validation-report.json", {
            "short": validation,
            "positioning": position_validation
        })
        shutil.copyfile(draft_dir / "script.md", root / "script.md")
        _write(root / "sources.json", draft["sources"])
        review = {
            "status": "review_required",
            "topic": topic,
            "narrative_mode": selected_mode,
            "source_family": source_family,
            "script": draft["script"],
            "sources": draft["sources"],
            "positioning": draft["script"]["positioning"],
            "validation": validation,
            "next_step": "Review cited primary sources and map checked claim IDs through web_handoff.py before paid media generation."
        }
        _write(root / "production-brief.json", review)
        manifest["status"] = "review_required"
        manifest["positioning"] = draft["script"]["positioning"]
        manifest["validation"] = validation
    _write(root / "manifest.json", manifest)
    return manifest

def package(output, dist):
    root, dist = Path(output), Path(dist)
    dist.mkdir(parents=True, exist_ok=True)
    wanted = ["manifest.json", "topic-case.json", "research-plan.json",
              "script.md", "sources.json", "positioning.json", "validation-report.json",
              "production-brief.json"]
    copied = []
    for name in wanted:
        src = root / name
        if src.is_file():
            shutil.copyfile(src, dist / name)
            copied.append(name)
    return {"status": "packaged", "files": copied, "publishable": False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("prepare")
    a.add_argument("--topic", required=True)
    a.add_argument("--angle", default="")
    a.add_argument("--output", default="outputs/satoshi-short")
    a.add_argument("--live", action="store_true")
    a.add_argument("--budget-usd", type=float, default=0)
    a.add_argument("--max-usd-per-run", type=float, default=0)
    a.add_argument("--model")
    a.add_argument("--max-tool-calls", type=int, default=6)
    b = sub.add_parser("package")
    b.add_argument("--output", default="outputs/satoshi-short")
    b.add_argument("--dist", default="dist")
    args = p.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.topic, args.angle, args.output, args.live,
                             args.budget_usd, args.max_usd_per_run, args.model,
                             args.max_tool_calls)
        else:
            result = package(args.output, args.dist)
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, RuntimeError, KeyError, TypeError) as exc:
        p.exit(1, "Satoshi short production blocked: %s\n" % exc)

if __name__ == "__main__":
    main()
