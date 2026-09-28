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


def _install_production_overrides():
    """Keep the live short path robust without broad changes to produce.py."""
    original_request_body = produce.request_body

    def request_body_with_headroom(case, plan, format_name, model, max_tool_calls=6):
        body = original_request_body(case, plan, format_name, model, max_tool_calls)
        body["max_output_tokens"] = max(int(body.get("max_output_tokens", 0)), 6000)
        return body

    def parse_response_with_web_provenance(result):
        """Accept only URLs actually returned by web_search, even when annotations are absent."""
        if result.get("status") != "completed":
            details = result.get("incomplete_details") or {}
            reason = details.get("reason") if isinstance(details, dict) else None
            error = result.get("error")
            raise ValueError(
                "Provider response not completed: status=%s; reason=%s; error=%s"
                % (result.get("status", "unknown"), reason or "unspecified", error or "none")
            )

        texts = []
        returned = {}
        annotated = {}
        for item in result.get("output", []):
            if item.get("type") == "web_search_call":
                for source in item.get("action", {}).get("sources", []):
                    url = source.get("url")
                    if isinstance(url, str) and url.startswith(("https://", "http://")):
                        returned[url] = {"url": url, "title": source.get("title", ""), "role": "consulted"}
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") != "output_text":
                    continue
                texts.append(content.get("text", ""))
                for note in content.get("annotations", []):
                    citation = note.get("url_citation", note)
                    if note.get("type") == "url_citation" and isinstance(citation.get("url"), str):
                        url = citation["url"]
                        annotated[url] = {"url": url, "title": citation.get("title", ""), "role": "cited"}

        if not texts:
            raise ValueError("Empty provider script")
        if not returned and not annotated:
            raise ValueError("Web-search draft returned no source provenance")

        script = produce._extract_json("".join(texts))
        available = {**returned, **annotated}
        used = set()
        for segment in script.get("segments", []):
            for url in segment.get("source_urls", []):
                if url not in available:
                    raise ValueError("Segment cites a URL that was not returned by web_search")
                used.add(url)
        receipt_url = script.get("positioning", {}).get("evidence_receipt_url")
        if isinstance(receipt_url, str) and receipt_url:
            if receipt_url not in available:
                raise ValueError("Positioning receipt URL was not returned by web_search")
            used.add(receipt_url)
        if not used:
            raise ValueError("Web-search draft does not reference returned sources")

        sources = []
        for url, source in available.items():
            entry = dict(source)
            if url in used:
                entry["role"] = "cited"
            sources.append(entry)
        return script, sorted(sources, key=lambda s: (s["url"], s["role"]))

    produce.request_body = request_body_with_headroom
    produce.parse_response = parse_response_with_web_provenance


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
    _install_production_overrides()
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
