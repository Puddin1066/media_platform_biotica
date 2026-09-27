"""Validate a chat-derived creative brief for Satoshi video production.

The request is intentionally small. ChatGPT can infer these fields from a normal
conversation and commit one JSON request. Editorial language is never treated as
evidence; the live research pipeline still has to support factual claims.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

OPENINGS = {"observation_first", "receipt_first", "wrinkle_first"}
MODELS = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"}


def _strings(value, name, limit=12):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit or any(not isinstance(x, str) for x in value):
        raise ValueError(f"{name} must be a list of at most {limit} strings")
    return [x.strip() for x in value if x.strip()]


def resolve(request):
    if not isinstance(request, dict):
        raise ValueError("request must be a JSON object")
    topic = str(request.get("topic", "")).strip()
    if not 3 <= len(topic) <= 300:
        raise ValueError("topic must contain 3-300 characters")
    opening = request.get("opening_strategy", "observation_first")
    if opening not in OPENINGS:
        raise ValueError("invalid opening_strategy")
    model = request.get("model", "gpt-5.6-sol")
    if model not in MODELS:
        raise ValueError("invalid model")
    try:
        budget = float(request.get("max_openai_usd", 1.0))
    except (TypeError, ValueError):
        raise ValueError("max_openai_usd must be numeric") from None
    if not 0 < budget <= 10:
        raise ValueError("max_openai_usd must be >0 and <=10")

    notes = str(request.get("editorial_notes", "")).strip()
    timing = str(request.get("timing_notes", "")).strip()
    candidate = _strings(request.get("candidate_lines"), "candidate_lines")
    must_keep = _strings(request.get("must_keep_lines"), "must_keep_lines", 8)
    avoid = _strings(request.get("avoid"), "avoid", 10)

    sections = [
        "CHAT-DERIVED EDITORIAL BRIEF. Creative direction only; factual claims still require web-researched evidence.",
        f"Preferred opening strategy: {opening}.",
    ]
    if notes:
        sections.append("Editorial angle/notes: " + notes)
    if candidate:
        sections.append("Candidate human lines/ideas (rewrite naturally if useful): " + " | ".join(candidate))
    if must_keep:
        sections.append(
            "Must-keep human phrasing where factually compatible; if a line embeds an unsupported factual claim, preserve the voice but correct the fact: "
            + " | ".join(must_keep)
        )
    if timing:
        sections.append("Timing/performance notes: " + timing)
    if avoid:
        sections.append("Avoid: " + " | ".join(avoid))
    sections.append(
        "Write one coherent spoken story. Do not concatenate these notes as blocks. Humor is optional and subordinate to interesting, credible content."
    )

    return {
        "schema_version": 1,
        "topic": topic,
        "opening_strategy": opening,
        "model": model,
        "max_openai_usd": budget,
        "angle": "\n".join(sections),
        "creative_brief": {
            "editorial_notes": notes,
            "candidate_lines": candidate,
            "must_keep_lines": must_keep,
            "timing_notes": timing,
            "avoid": avoid,
        },
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    resolved = resolve(json.loads(Path(args.input).read_text(encoding="utf-8")))
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(resolved, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
