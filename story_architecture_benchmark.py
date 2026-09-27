"""A/B harness for six-stage story architecture using one shared evidence bundle.

Research happens once with web_search. Both writer arms receive the same vetted
receipt bundle and cite source IDs, never URLs. This keeps the A/B focused on
story architecture and prevents writer-generated URL fabrication.
"""
from __future__ import annotations

import argparse
import json
import os
import random
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import produce
import story_architecture

BENCHMARK_MAX_OUTPUT_TOKENS = 8000
RESEARCH_MAX_OUTPUT_TOKENS = 5000
TRACKING_QUERY_KEYS = {"gclid", "fbclid", "mc_cid", "mc_eid"}

RECEIPT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["receipts"],
    "properties": {"receipts": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["claim", "source_url", "source_title"],
        "properties": {
            "claim": {"type": "string"},
            "source_url": {"type": "string"},
            "source_title": {"type": "string"},
        },
    }}},
}

WRITER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["title", "segments", "open_question", "callback_anchor", "positioning"],
    "properties": {
        "title": {"type": "string"},
        "open_question": {"type": "string"},
        "callback_anchor": {"type": "string"},
        "positioning": {
            "type": "object", "additionalProperties": False,
            "required": ["territory", "male_consequence", "prevailing_belief", "evidence_conflict",
                         "evidence_receipt", "evidence_receipt_source_id", "audience_tension",
                         "share_trigger", "positioned_premise", "hook_variants"],
            "properties": {
                "territory": {"type": "string"}, "male_consequence": {"type": "string"},
                "prevailing_belief": {"type": "string"}, "evidence_conflict": {"type": "string"},
                "evidence_receipt": {"type": "string"}, "evidence_receipt_source_id": {"type": "string"},
                "audience_tension": {"type": "string"}, "share_trigger": {"type": "string"},
                "positioned_premise": {"type": "string"},
                "hook_variants": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["type", "text"],
                    "properties": {"type": {"type": "string"}, "text": {"type": "string"}},
                }},
            },
        },
        "segments": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "required": ["beat", "text", "source_ids", "production_note", "monologue_moves"],
            "properties": {
                "beat": {"type": "string"}, "text": {"type": "string"},
                "source_ids": {"type": "array", "items": {"type": "string"}},
                "production_note": {"type": "string"},
                "monologue_moves": {"type": "array", "items": {
                    "type": "object", "additionalProperties": False,
                    "required": ["function", "text"],
                    "properties": {"function": {"type": "string"}, "text": {"type": "string"}},
                }},
            },
        }},
    },
}


def _provider_failure(result):
    status = result.get("status", "unknown")
    details = result.get("incomplete_details") or {}
    reason = details.get("reason") if isinstance(details, dict) else None
    return f"status={status}; reason={reason or 'unspecified'}; error={result.get('error') or 'none'}"


def _canonical_url(url):
    if not isinstance(url, str):
        return ""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    host = parts.hostname.lower()
    path = (parts.path or "/").rstrip("/") or "/"
    query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in TRACKING_QUERY_KEYS:
            continue
        query.append((key, value))
    query.sort()
    return urlunsplit((parts.scheme.lower(), host, path, urlencode(query, doseq=True), ""))


def research_body(case, plan, model, max_tool_calls=6):
    return {
        "model": model,
        "store": False,
        "instructions": (
            "Research the question using web_search. Return concise factual receipts useful for a men's-health story. "
            "Prefer primary papers, government/regulatory sources, registries, and strong reviews. Include challenging "
            "evidence and uncertainty. source_url must be a URL you actually found through web_search; never construct a URL."
        ),
        "input": json.dumps({"question": case["question"], "hypotheses": case["hypotheses"], "search_cues": plan}, ensure_ascii=False),
        "tools": [{"type": "web_search"}], "tool_choice": "auto",
        "include": ["web_search_call.action.sources"], "max_tool_calls": max_tool_calls,
        "max_output_tokens": RESEARCH_MAX_OUTPUT_TOKENS,
        "text": {"format": {"type": "json_schema", "name": "receipt_bundle", "strict": True, "schema": RECEIPT_SCHEMA}},
    }


def _parse_research(result):
    if result.get("status") != "completed":
        raise ValueError("Research response not completed: " + _provider_failure(result))
    texts, returned = [], {}
    for item in result.get("output", []):
        if item.get("type") == "web_search_call":
            for source in item.get("action", {}).get("sources", []):
                url = source.get("url")
                if isinstance(url, str) and url.startswith(("http://", "https://")):
                    returned.setdefault(_canonical_url(url), {"url": url, "title": source.get("title", "")})
        elif item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    texts.append(content.get("text", ""))
    if not texts or not returned:
        raise ValueError("Research produced no usable text or web sources")
    draft = produce._extract_json("".join(texts))
    receipts = []
    seen = set()
    for row in draft.get("receipts", []):
        matched = returned.get(_canonical_url(row.get("source_url")))
        claim = str(row.get("claim", "")).strip()
        if not matched or not claim:
            continue
        key = (claim.lower(), matched["url"])
        if key in seen:
            continue
        seen.add(key)
        receipts.append({"source_id": f"S{len(receipts)+1}", "claim": claim,
                         "title": matched.get("title") or str(row.get("source_title", "")),
                         "url": matched["url"]})
    if len(receipts) < 2:
        raise ValueError("Research produced fewer than two web-grounded receipts")
    return receipts


def writer_body(case, format_name, model, receipts, six_stage=False):
    brief = {
        "case_question": case["question"], "canon": case["canon"], "hypotheses": case["hypotheses"],
        "format": format_name, "target_length": produce.FORMATS[format_name], "required_beats": produce.BEATS,
        "reference_mechanics": produce.corpus_mechanics(case),
        "evidence_bundle": [{"source_id": r["source_id"], "claim": r["claim"], "title": r["title"]} for r in receipts],
        "assignment": (
            "Write the requested Satoshi Shkreli media draft using only evidence_bundle for factual claims. "
            "Cite receipts only by source_id; never output, infer, reconstruct, or guess a URL. Every factual segment needs "
            "at least one valid source_id. For short format target 60–85 spoken words and never exceed 95. Use the five beats "
            "opening, explanations, evidence, limits, next_test. Opening: cold_open, comic_turn; explanations: stakes, escalation; "
            "evidence: receipt, reveal; limits: reversal, qualification; next_test: callback, button. Each segment must contain exactly "
            "those two monologue_moves in order and segment.text must equal their texts joined by one space. Use exactly three materially "
            "different hook variants. Keep uncertainty explicit and do not give treatment advice."
        ),
    }
    if six_stage:
        brief["story_architecture"] = story_architecture.build(case, format_name)
        brief["story_to_production_beats"] = story_architecture.beat_mapping()
        brief["assignment"] += (
            " Before drafting, resolve the story as prevailing belief; belief origin; strongest destabilizing receipt; central anomaly; "
            "at least two plausible competing explanations when evidence permits; and Satoshi's synthesis with residual uncertainty. "
            "Then compress that causal story into the five production beats."
        )
    return {
        "model": model, "store": False,
        "instructions": "Write for an original skeptical, witty men's-health host. Evidence bundle is authoritative; source IDs are references, not prose.",
        "input": json.dumps(brief, ensure_ascii=False),
        "max_output_tokens": BENCHMARK_MAX_OUTPUT_TOKENS,
        "text": {"format": {"type": "json_schema", "name": "receipt_backed_script", "strict": True, "schema": WRITER_SCHEMA}},
    }


def build_pair(case, plan, format_name, model, max_tool_calls=6, receipts=None):
    receipts = receipts or [{"source_id": "S1", "claim": "fixture claim", "title": "fixture source", "url": "https://example.org/fixture"}]
    return {
        "baseline": writer_body(case, format_name, model, receipts, six_stage=False),
        "six_stage": writer_body(case, format_name, model, receipts, six_stage=True),
    }


def _parse_writer(result):
    if result.get("status") != "completed":
        raise ValueError("Writer response not completed: " + _provider_failure(result))
    texts = []
    for item in result.get("output", []):
        if item.get("type") == "message":
            texts.extend(c.get("text", "") for c in item.get("content", []) if c.get("type") == "output_text")
    if not texts:
        raise ValueError("Writer returned no script")
    return produce._extract_json("".join(texts))


def _materialize_source_urls(script, receipts):
    by_id = {r["source_id"]: r for r in receipts}
    out = {k: v for k, v in script.items() if k != "positioning" and k != "segments"}
    segments = []
    for segment in script.get("segments", []):
        ids = segment.get("source_ids")
        if not isinstance(ids, list) or not ids or any(i not in by_id for i in ids):
            raise ValueError(f"Writer used unknown or missing source_id: {ids}")
        segments.append({"beat": segment["beat"], "text": segment["text"],
                         "source_urls": [by_id[i]["url"] for i in ids],
                         "production_note": segment["production_note"], "monologue_moves": segment["monologue_moves"]})
    p = dict(script.get("positioning", {}))
    receipt_id = p.pop("evidence_receipt_source_id", None)
    if receipt_id not in by_id:
        raise ValueError(f"Writer used unknown evidence receipt source_id: {receipt_id}")
    p["evidence_receipt_url"] = by_id[receipt_id]["url"]
    out["segments"] = segments
    out["positioning"] = p
    allowed = [r["url"] for r in receipts]
    produce.check_script(out, allowed)
    return out


def _run_writer(body, credential, receipts):
    result = produce.call_openai(body, credential)
    script = _materialize_source_urls(_parse_writer(result), receipts)
    return {"script": script, "sources": receipts, "usage": result.get("usage", {})}


def run_live(case, plan, format_name, model, output, max_tool_calls=6):
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    credential = os.environ.get("OPENAI_API_KEY")
    if not credential:
        raise ValueError("OPENAI_API_KEY missing")
    research_result = produce.call_openai(research_body(case, plan, model, max_tool_calls), credential)
    receipts = _parse_research(research_result)
    pair = build_pair(case, plan, format_name, model, max_tool_calls, receipts=receipts)
    results = {name: _run_writer(body, credential, receipts) for name, body in pair.items()}
    labels = ["baseline", "six_stage"]
    random.SystemRandom().shuffle(labels)
    blind = {"A": results[labels[0]], "B": results[labels[1]], "shared_receipts": receipts}
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    (root / "blind-packet.json").write_text(json.dumps(blind, indent=2), encoding="utf-8")
    (root / "blind-key.json").write_text(json.dumps({"A": labels[0], "B": labels[1]}, indent=2), encoding="utf-8")
    return {"status": "human_review_required", "packet": str(root / "blind-packet.json"),
            "key": str(root / "blind-key.json"), "receipt_count": len(receipts), "publishable": False}


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
        result = {"status": "dry_run", "baseline_has_story_architecture": "story_architecture" in baseline,
                  "six_stage_has_story_architecture": "story_architecture" in six_stage,
                  "same_evidence_bundle": baseline["evidence_bundle"] == six_stage["evidence_bundle"],
                  "writer_has_web_search": bool(pair["baseline"].get("tools") or pair["six_stage"].get("tools")),
                  "publishable": False}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
