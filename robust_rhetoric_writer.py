"""Bounded-retry Responses helper for rhetoric candidate generation."""
from __future__ import annotations

from corpus_embeddings import _openai_json
from semantic_rhetoric import RESPONSES_ENDPOINT


def response_text(model: str, instructions: str, prompt: str, key: str, reasoning: str | None = None) -> str:
    """Generate candidate text with one bounded retry if reasoning exhausts output budget."""
    last_status = None
    for max_output_tokens in (1400, 2400):
        body = {
            "model": model,
            "store": False,
            "instructions": instructions,
            "input": prompt,
            "max_output_tokens": max_output_tokens,
        }
        if reasoning:
            body["reasoning"] = {"effort": reasoning}
        result = _openai_json(RESPONSES_ENDPOINT, body, key)
        last_status = result.get("status")
        if last_status != "completed":
            continue
        text = "".join(
            part.get("text", "")
            for item in result.get("output", []) if item.get("type") == "message"
            for part in item.get("content", []) if part.get("type") == "output_text"
        ).strip()
        if text:
            return text
    raise ValueError(f"Writer response incomplete after bounded retry; last_status={last_status}")
