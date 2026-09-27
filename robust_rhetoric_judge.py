"""Robust blind editorial judge for rhetoric benchmarks."""
from __future__ import annotations

import json

from corpus_embeddings import _openai_json
from openai_models import model_for, reasoning_for
from semantic_rhetoric import DIMENSIONS, RESPONSES_ENDPOINT


def _parse(result: dict) -> dict | None:
    if result.get("status") != "completed":
        return None
    raw = "".join(
        part.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    ).strip()
    return json.loads(raw) if raw else None


def judge(brief: dict, a: str, b: str, key: str) -> dict:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["A", "B", "preferred"],
        "properties": {
            "A": {
                "type": "object",
                "additionalProperties": False,
                "required": list(DIMENSIONS),
                "properties": {d: {"type": "number", "minimum": 1, "maximum": 5} for d in DIMENSIONS},
            },
            "B": {
                "type": "object",
                "additionalProperties": False,
                "required": list(DIMENSIONS),
                "properties": {d: {"type": "number", "minimum": 1, "maximum": 5} for d in DIMENSIONS},
            },
            "preferred": {"type": "string", "enum": ["A", "B", "tie"]},
        },
    }
    body = {
        "model": model_for("editorial_reasoning"),
        "store": False,
        "reasoning": {"effort": reasoning_for("editorial_reasoning") or "high"},
        "instructions": (
            "Act as a blind editorial evaluator. Score only writing quality against the supplied evidence brief. "
            "Prioritize hook strength, coherence, evidence handling, originality, and audience fit. "
            "Do not infer which candidate used retrieval."
        ),
        "input": f"TOPIC: {brief['topic']}\nEVIDENCE: {brief['evidence']}\n\nCANDIDATE A:\n{a}\n\nCANDIDATE B:\n{b}",
        "max_output_tokens": 1800,
        "text": {"format": {"type": "json_schema", "name": "rhetoric_benchmark_score", "strict": True, "schema": schema}},
    }
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    parsed = _parse(result)
    if parsed is not None:
        return parsed

    # One bounded retry with more output headroom. This addresses reasoning-budget exhaustion
    # without changing model, rubric, candidate order, or evidence.
    body["max_output_tokens"] = 3200
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    parsed = _parse(result)
    if parsed is None:
        raise ValueError(f"Judge response incomplete after retry: {result.get('status')}")
    return parsed
