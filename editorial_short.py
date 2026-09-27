"""Low-cost editorial short writer for Biotica Media.

The writer consumes a pre-researched receipt bundle. It never performs web search
and never creates URLs. Four editorial beats define the reasoning underneath the
story, but they are not independently rendered prose blocks. A constrained opening
strategy is selected first, then the model writes one coherent script end to end.
"""
from __future__ import annotations

import json

import produce

BEATS = ["interesting_thing", "receipt", "meaning", "remaining_weirdness"]
OPENING_STRATEGIES = {
    "observation_first": "Begin with the genuinely interesting observation, contradiction, or change.",
    "receipt_first": "Begin with the strongest concrete study, trial, dataset, regulatory event, or other receipt.",
    "wrinkle_first": "Begin with the unresolved wrinkle or contradiction, then earn the explanation with evidence.",
}
TARGET_WORDS = "60-85 spoken words; never exceed 95"

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["title", "opening_strategy", "script_text", "beats", "open_question"],
    "properties": {
        "title": {"type": "string"},
        "opening_strategy": {"type": "string", "enum": sorted(OPENING_STRATEGIES)},
        "script_text": {"type": "string"},
        "open_question": {"type": "string"},
        "beats": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["beat", "summary", "source_ids", "production_note"],
                "properties": {
                    "beat": {"type": "string"},
                    "summary": {"type": "string"},
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


def request_body(case, model, receipts, opening_strategy="observation_first"):
    """Build a cheap no-search writing request from a vetted receipt bundle."""
    if not receipts:
        raise ValueError("At least one vetted receipt is required")
    if opening_strategy not in OPENING_STRATEGIES:
        raise ValueError(f"Unknown opening strategy: {opening_strategy}")
    brief = {
        "case_question": case["question"],
        "canon": case.get("canon", ""),
        "evidence_bundle": _public_receipts(receipts),
        "target_length": TARGET_WORDS,
        "editorial_reasoning": BEATS,
        "opening_strategy": opening_strategy,
        "opening_instruction": OPENING_STRATEGIES[opening_strategy],
        "assignment": (
            "Write a short men's-health science story that feels like editorial content, not an advertisement. "
            "Use only evidence_bundle for factual claims and cite it only by source_id. Never output, infer, or reconstruct URLs. "
            "The underlying editorial reasoning must cover: interesting_thing, receipt, meaning, and remaining_weirdness. "
            "These are semantic checkpoints, not four prose blocks and not a required spoken order. "
            "Follow opening_instruction for the first sentence, then rewrite the ENTIRE piece as one coherent narrative with natural transitions. "
            "Do not concatenate modular beat text. script_text must be the actual continuous spoken script. "
            "Use beats only as compact metadata explaining where each editorial function is satisfied and which receipts support it. "
            "Avoid direct-response language, fake urgency, generic engagement bait, and calls to subscribe. "
            "Keep uncertainty explicit. If evidence is weak, say so instead of manufacturing drama."
        ),
    }
    return {
        "model": model,
        "store": False,
        "instructions": (
            "Write for Satoshi Shkreli, an original skeptical, witty men's-health host. "
            "Prioritize interesting science, concrete evidence, coherent editorial reasoning, and intelligent uncertainty over persuasion."
        ),
        "input": json.dumps(brief, ensure_ascii=False),
        "max_output_tokens": 1800,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "editorial_short",
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
        texts.extend(c.get("text", "") for c in item.get("content", []) if c.get("type") == "output_text")
    if not texts:
        raise ValueError("Writer returned no script")
    return produce._extract_json("".join(texts))


def materialize(script, receipts):
    """Validate source IDs and attach exact research URLs after writing."""
    by_id = {r["source_id"]: r for r in receipts}
    expected_fields = {"title", "opening_strategy", "script_text", "beats", "open_question"}
    if set(script) != expected_fields:
        raise ValueError("Invalid editorial short fields")
    if script["opening_strategy"] not in OPENING_STRATEGIES:
        raise ValueError("Invalid opening strategy")
    spoken = script.get("script_text", "").strip()
    if not spoken:
        raise ValueError("Continuous script_text is required")
    if len(spoken.split()) > 95:
        raise ValueError("Short script exceeds 95 spoken words")
    beats = script.get("beats")
    if not isinstance(beats, list) or len(beats) != len(BEATS):
        raise ValueError("Expected exactly four editorial checkpoints")
    annotations = []
    for row, expected in zip(beats, BEATS):
        if row.get("beat") != expected:
            raise ValueError("Editorial checkpoints are missing or out of canonical reasoning order")
        ids = row.get("source_ids")
        if not isinstance(ids, list) or not ids or any(i not in by_id for i in ids):
            raise ValueError(f"Unknown or missing source_id: {ids}")
        summary = row.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("Editorial checkpoint summary is required")
        annotations.append({
            "beat": expected,
            "summary": summary,
            "source_urls": [by_id[i]["url"] for i in ids],
            "production_note": row.get("production_note", ""),
        })
    return {
        "title": script["title"],
        "opening_strategy": script["opening_strategy"],
        "script_text": spoken,
        "open_question": script["open_question"],
        "editorial_annotations": annotations,
        "sources": receipts,
        "publishable": False,
    }
