"""Low-cost editorial short writer for Biotica Media.

The writer consumes a pre-researched receipt bundle. It never performs web search
and never creates URLs. The default short structure is deliberately simple:
interesting thing -> receipt -> what it means -> what's still weird.
"""
from __future__ import annotations

import json

import produce

BEATS = ["interesting_thing", "receipt", "meaning", "remaining_weirdness"]
TARGET_WORDS = "60-85 spoken words; never exceed 95"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "beats", "open_question"],
    "properties": {
        "title": {"type": "string"},
        "open_question": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["beat", "text", "source_ids", "production_note"],
                "properties": {
                    "beat": {"type": "string"},
                    "text": {"type": "string"},
                    "source_ids": {"type": "array", "items": {"type": "string"}},
                    "production_note": {"type": "string"},
                },
            },
        },
    },
}


def _public_receipts(receipts):
    return [
        {"source_id": r["source_id"], "claim": r["claim"], "title": r.get("title", "")}
        for r in receipts
    ]


def request_body(case, model, receipts):
    """Build a cheap no-search writing request from a vetted receipt bundle."""
    if not receipts:
        raise ValueError("At least one vetted receipt is required")
    brief = {
        "case_question": case["question"],
        "canon": case.get("canon", ""),
        "evidence_bundle": _public_receipts(receipts),
        "target_length": TARGET_WORDS,
        "required_beats": BEATS,
        "assignment": (
            "Write a short men's-health science story that feels like editorial content, not an advertisement. "
            "Use only evidence_bundle for factual claims and cite it only by source_id. Never output, infer, or reconstruct URLs. "
            "Use exactly four beats in order. interesting_thing: open with the genuinely interesting observation, contradiction, or change. "
            "receipt: give the strongest concrete study, trial, dataset, regulatory event, or other receipt. "
            "meaning: explain what the receipt changes or suggests without overselling it. "
            "remaining_weirdness: end on the unresolved wrinkle, limitation, competing explanation, or question that is actually interesting. "
            "Avoid direct-response language, fake urgency, generic engagement bait, and calls to subscribe. "
            "Keep the spoken rhythm natural and compact. If evidence is weak, say so instead of manufacturing drama."
        ),
    }
    return {
        "model": model,
        "store": False,
        "instructions": (
            "Write for Satoshi Shkreli, an original skeptical, witty men's-health host. "
            "Prioritize interesting science, concrete evidence, and intelligent uncertainty over persuasion."
        ),
        "input": json.dumps(brief, ensure_ascii=False),
        "max_output_tokens": 1800,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "editorial_four_beat_short",
                "strict": True,
                "schema": SCHEMA,
            }
        },
    }


def parse_response(result):
    if result.get("status") != "completed":
        raise ValueError("Writer response incomplete or refused")
    texts = []
    for item in result.get("output", []):
        if item.get("type") != "message":
            continue
        texts.extend(
            c.get("text", "") for c in item.get("content", [])
            if c.get("type") == "output_text"
        )
    if not texts:
        raise ValueError("Writer returned no script")
    return produce._extract_json("".join(texts))


def materialize(script, receipts):
    """Map writer source IDs back to exact research URLs after writing."""
    by_id = {r["source_id"]: r for r in receipts}
    if set(script) != {"title", "beats", "open_question"}:
        raise ValueError("Invalid editorial short fields")
    beats = script.get("beats")
    if not isinstance(beats, list) or len(beats) != len(BEATS):
        raise ValueError("Expected exactly four editorial beats")
    out_beats = []
    for row, expected in zip(beats, BEATS):
        if row.get("beat") != expected:
            raise ValueError("Editorial beats are missing or out of order")
        ids = row.get("source_ids")
        if not isinstance(ids, list) or not ids or any(i not in by_id for i in ids):
            raise ValueError(f"Unknown or missing source_id: {ids}")
        text = row.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Editorial beat text is required")
        out_beats.append({
            "beat": expected,
            "text": text,
            "source_urls": [by_id[i]["url"] for i in ids],
            "production_note": row.get("production_note", ""),
        })
    return {
        "title": script["title"],
        "open_question": script["open_question"],
        "beats": out_beats,
        "sources": receipts,
        "publishable": False,
    }
