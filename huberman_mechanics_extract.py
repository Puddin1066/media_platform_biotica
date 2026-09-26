"""Derive neutralized rhetorical mechanics from private Huberman transcript snapshots.

The source transcript remains private/transient. Output is structural metadata only.
The prompt explicitly forbids imitation, creator-specific phrasing, factual reuse,
and direct quotations. Generated mechanics must be independently useful as abstract
writing moves for Biotica/Satoshi.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.request
from pathlib import Path

from openai_models import model_for

RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
MAX_SOURCE_CHARS = 45000
MAX_NGRAM_WORDS = 8

SYSTEM = """You are an editorial-structure analyst.
Analyze the supplied transcript excerpt only for transferable explanatory mechanics.
Do NOT imitate Andrew Huberman or reproduce his voice, cadence, jokes, catchphrases,
creator-specific phrasing, or factual claims. Do NOT quote the transcript.
Return abstract narrative mechanics in neutral language that another writer could use
without sounding like the source creator. Focus on structure: hooks, sequencing,
mechanism explanation, transitions, evidence qualification, counter-case handling,
recaps, practical implications, and callbacks.
"""


def _request_payload(source_text: str, episode_id: str) -> dict:
    prompt = {
        "episode_id": episode_id,
        "task": "derive 5-10 distinct neutral rhetorical mechanics",
        "required_fields": ["function", "mechanic", "when_to_use", "avoid"],
        "forbidden": [
            "direct quotes",
            "source facts",
            "creator-specific phrasing",
            "voice imitation",
            "references to Andrew Huberman in the mechanic text",
        ],
        "source_excerpt": source_text[:MAX_SOURCE_CHARS],
    }
    return {
        "model": model_for("classification").model,
        "input": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(prompt)},
        ],
        "text": {"format": {"type": "json_object"}},
    }


def _call_openai(payload: dict) -> dict:
    if os.environ.get("OPENAI_LIVE_ENABLED", "").lower() != "true":
        raise RuntimeError("OPENAI_LIVE_ENABLED=true is required")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required")
    req = urllib.request.Request(
        RESPONSES_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def _response_text(response: dict) -> str:
    for item in response.get("output", []):
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"} and content.get("text"):
                return content["text"]
    if response.get("output_text"):
        return response["output_text"]
    raise ValueError("No text output returned")


def _word_ngrams(text: str, n: int) -> set[tuple[str, ...]]:
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    return {tuple(words[i:i+n]) for i in range(max(0, len(words)-n+1))}


def validate_neutralized(source_text: str, result: dict) -> dict:
    mechanics = result.get("mechanics")
    if not isinstance(mechanics, list) or not 5 <= len(mechanics) <= 10:
        raise ValueError("Expected 5-10 mechanics")
    source_ngrams = _word_ngrams(source_text, MAX_NGRAM_WORDS)
    for item in mechanics:
        if set(item) != {"function", "mechanic", "when_to_use", "avoid"}:
            raise ValueError("Invalid mechanic fields")
        for key, value in item.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Mechanic fields must be non-empty strings")
        joined = " ".join(item.values())
        if "huberman" in joined.lower():
            raise ValueError("Neutralized mechanics may not reference the source creator")
        if source_ngrams and (_word_ngrams(joined, MAX_NGRAM_WORDS) & source_ngrams):
            raise ValueError("Mechanic contains excessive verbatim overlap with source")
    return result


def derive(source_path: Path, episode_id: str) -> dict:
    source_text = source_path.read_text(encoding="utf-8")
    response = _call_openai(_request_payload(source_text, episode_id))
    parsed = json.loads(_response_text(response))
    validate_neutralized(source_text, parsed)
    return {
        "schema_version": 1,
        "episode_id": episode_id,
        "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "source_text_included": False,
        "creator_voice_imitation": False,
        "mechanics": parsed["mechanics"],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", required=True)
    p.add_argument("--episode-id", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = derive(Path(args.source), args.episode_id)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
