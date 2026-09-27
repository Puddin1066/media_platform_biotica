"""A/B harness for six-stage story architecture versus the current writer.

The experiment leaves production unchanged. It builds two otherwise-equivalent
OpenAI web-search requests: baseline and six-stage architecture conditioned.
Live mode writes a blinded human-review packet plus a separate key.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from copy import deepcopy
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import produce
import story_architecture

BENCHMARK_MAX_OUTPUT_TOKENS = 8000
TRACKING_QUERY_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid"}


def architecture_body(case, plan, format_name, model, max_tool_calls=6):
    body = produce.request_body(case, plan, format_name, model, max_tool_calls)
    brief = json.loads(body["input"])
    brief["story_architecture"] = story_architecture.build(case, format_name)
    brief["story_to_production_beats"] = story_architecture.beat_mapping()
    brief["assignment"] += (
        " Before drafting the production beats, resolve the story in story_architecture sequence: "
        "prevailing belief; why that belief formed; the strongest destabilizing receipt; the central anomaly; "
        "at least two plausible competing explanations when evidence permits; and Satoshi's synthesis with residual uncertainty. "
        "Background earns space only when it explains why the next turn happened. Do not output a list of disconnected facts. "
        "Then compress that causal story into the existing required_beats using story_to_production_beats as guidance; "
        "the production beat schema remains authoritative."
    )
    body["input"] = json.dumps(brief, ensure_ascii=False)
    return body


def build_pair(case, plan, format_name, model, max_tool_calls=6):
    pair = {
        "baseline": produce.request_body(case, plan, format_name, model, max_tool_calls),
        "six_stage": architecture_body(case, plan, format_name, model, max_tool_calls),
    }
    for body in pair.values():
        body["max_output_tokens"] = BENCHMARK_MAX_OUTPUT_TOKENS
    return pair


def _provider_failure(result):
    status = result.get("status", "unknown")
    details = result.get("incomplete_details") or {}
    reason = details.get("reason") if isinstance(details, dict) else None
    error = result.get("error")
    return f"status={status}; reason={reason or 'unspecified'}; error={error or 'none'}"


def _parse_benchmark_response(result):
    """Parse structured output while grounding URLs in returned web-search sources.

    Responses structured JSON may contain the requested source_urls without also
    attaching url_citation annotations to the JSON text. For this experiment we
    therefore accept the explicit web_search_call.action.sources list as the
    evidence allowlist. This is deliberately benchmark-only; production keeps its
    stricter citation-annotation requirement.
    """
    if result.get("status") != "completed":
        raise ValueError("Provider response not completed: " + _provider_failure(result))

    texts = []
    sources = {}
    for item in result.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []):
                url = source.get("url")
                if isinstance(url, str) and url.startswith(("https://", "http://")):
                    sources[url] = {
                        "url": url,
                        "title": source.get("title", ""),
                        "role": "consulted",
                    }
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") != "output_text":
                    continue
                texts.append(content.get("text", ""))
                for note in content.get("annotations", []):
                    citation = note.get("url_citation", note)
                    if note.get("type") == "url_citation" and isinstance(citation.get("url"), str):
                        url = citation["url"]
                        sources[url] = {
                            "url": url,
                            "title": citation.get("title", ""),
                            "role": "cited",
                        }

    if not texts:
        raise ValueError("Empty provider script")
    if not sources:
        raise ValueError("Web-search draft lacks returned sources")

    script = produce._extract_json("".join(texts))
    return script, sorted(sources.values(), key=lambda s: (s["url"], s["role"]))


def _canonical_url(url):
    """Normalize non-semantic URL differences without broadening source identity."""
    if not isinstance(url, str):
        return ""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    host = parts.hostname.lower()
    port = parts.port
    if port and not ((parts.scheme.lower() == "http" and port == 80) or
                     (parts.scheme.lower() == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in TRACKING_QUERY_KEYS:
            continue
        query.append((key, value))
    query.sort()
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query, doseq=True), ""))


def _reconcile_script_urls(script, allowed_urls):
    """Map benign URL variants to exact provider-returned URLs; reject the rest."""
    canonical_to_exact = {}
    for url in allowed_urls:
        canonical = _canonical_url(url)
        if canonical:
            canonical_to_exact.setdefault(canonical, url)

    out = deepcopy(script)

    def reconcile(url):
        if url in allowed_urls:
            return url
        matched = canonical_to_exact.get(_canonical_url(url))
        if not matched:
            raise ValueError(f"Script cites URL not returned by web search: {url}")
        return matched

    for segment in out.get("segments", []):
        if isinstance(segment, dict) and isinstance(segment.get("source_urls"), list):
            segment["source_urls"] = [reconcile(url) for url in segment["source_urls"]]

    positioning = out.get("positioning")
    if isinstance(positioning, dict) and isinstance(positioning.get("evidence_receipt_url"), str):
        positioning["evidence_receipt_url"] = reconcile(positioning["evidence_receipt_url"])

    return out


def _run_arm(body, credential):
    result = produce.call_openai(body, credential)
    script, sources = _parse_benchmark_response(result)
    allowed_urls = [s["url"] for s in sources]
    script = _reconcile_script_urls(script, allowed_urls)
    produce.check_script(script, allowed_urls)
    return {"script": script, "sources": sources, "usage": result.get("usage", {})}


def run_live(case, plan, format_name, model, output, max_tool_calls=6):
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    credential = os.environ.get("OPENAI_API_KEY")
    if not credential:
        raise ValueError("OPENAI_API_KEY missing")
    pair = build_pair(case, plan, format_name, model, max_tool_calls)
    results = {name: _run_arm(body, credential) for name, body in pair.items()}

    labels = ["baseline", "six_stage"]
    random.SystemRandom().shuffle(labels)
    blind = {"A": results[labels[0]], "B": results[labels[1]]}
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    (root / "blind-packet.json").write_text(json.dumps(blind, indent=2), encoding="utf-8")
    (root / "blind-key.json").write_text(
        json.dumps({"A": labels[0], "B": labels[1]}, indent=2), encoding="utf-8")
    return {
        "status": "human_review_required",
        "packet": str(root / "blind-packet.json"),
        "key": str(root / "blind-key.json"),
        "publishable": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default="cases/mens-health.json")
    parser.add_argument("--plan", default="cases/research-plan.json")
    parser.add_argument("--format", default="short")
    parser.add_argument("--model", default=os.environ.get("OPENAI_CREATIVE_MODEL", os.environ.get("OPENAI_MODEL", "gpt-5.6-sol")))
    parser.add_argument("--max-tool-calls", type=int, default=6)
    parser.add_argument("--output", default="outputs/story-architecture-ab")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()

    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    if args.live:
        result = run_live(case, plan, args.format, args.model, args.output, args.max_tool_calls)
    else:
        pair = build_pair(case, plan, args.format, args.model, args.max_tool_calls)
        baseline = json.loads(pair["baseline"]["input"])
        six_stage = json.loads(pair["six_stage"]["input"])
        result = {
            "status": "dry_run",
            "baseline_has_story_architecture": "story_architecture" in baseline,
            "six_stage_has_story_architecture": "story_architecture" in six_stage,
            "same_tools": pair["baseline"]["tools"] == pair["six_stage"]["tools"],
            "same_output_schema": pair["baseline"]["text"] == pair["six_stage"]["text"],
            "same_output_budget": pair["baseline"]["max_output_tokens"] == pair["six_stage"]["max_output_tokens"],
            "max_output_tokens": pair["baseline"]["max_output_tokens"],
            "publishable": False,
        }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
