"""Validate a chat-derived creative brief for Satoshi video production.

The request preserves the useful parts of a conversation as structured creative
inputs. Editorial language is never treated as evidence; factual candidates are
explicitly marked for live web verification before they can enter narration.
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
    thesis = str(request.get("core_thesis", "")).strip()
    timing = str(request.get("timing_notes", "")).strip()
    candidate = _strings(request.get("candidate_lines"), "candidate_lines")
    must_keep = _strings(request.get("must_keep_lines"), "must_keep_lines", 8)
    avoid = _strings(request.get("avoid"), "avoid", 10)
    questions = _strings(request.get("open_questions"), "open_questions", 10)
    suspicions = _strings(request.get("suspicions"), "suspicions", 10)
    analogies = _strings(request.get("historical_analogies"), "historical_analogies", 10)
    visuals = _strings(request.get("visual_ideas"), "visual_ideas", 10)
    claims = _strings(request.get("claims_to_verify"), "claims_to_verify", 16)
    supplied_urls = _strings(request.get("supplied_urls"), "supplied_urls", 16)

    host_mode = str(request.get("host_mode", "avatar")).strip() or "avatar"
    if host_mode not in {"avatar", "uploaded_plate"}:
        raise ValueError("host_mode must be avatar or uploaded_plate")
    visual_mode = str(request.get("visual_mode", "lean")).strip().casefold() or "lean"
    if visual_mode not in {"lean", "ai"}:
        raise ValueError("visual_mode must be lean or ai")
    plate_r2_key = str(request.get("plate_r2_key", "")).strip()
    plate_local_path = str(request.get("plate_local_path", "")).strip()
    dialogue_avatar_id = str(request.get("dialogue_avatar_id", "")).strip()
    dialogue_notes = str(request.get("dialogue_notes", "")).strip()
    if host_mode == "uploaded_plate" and not plate_r2_key and not plate_local_path:
        raise ValueError("uploaded_plate requires plate_r2_key or plate_local_path")
    if dialogue_avatar_id and host_mode != "uploaded_plate":
        # Reserved for a future Satoshi↔counterpart Reel; currently recorded only.
        pass

    sections = [
        "CHAT-DERIVED EDITORIAL BRIEF. Creative direction only; factual claims still require web-researched evidence.",
        f"Preferred opening strategy: {opening}.",
        f"Host mode: {host_mode}.",
        f"Visual mode: {visual_mode}.",
    ]
    if plate_r2_key:
        sections.append("Filmed plate R2 key (on-camera body): " + plate_r2_key)
    if plate_local_path:
        sections.append("Filmed plate local path (on-camera body): " + plate_local_path)
    if dialogue_avatar_id or dialogue_notes:
        sections.append(
            "Optional dialogue counterpart requested; short pipeline still renders a "
            "single-host monologue until dual-avatar dialogue is implemented. Notes: "
            + (dialogue_notes or dialogue_avatar_id)
        )
    if thesis:
        sections.append("Core human thesis: " + thesis)
    if notes:
        sections.append("Editorial angle/notes: " + notes)
    if candidate:
        sections.append("Candidate human lines/ideas (rewrite naturally if useful): " + " | ".join(candidate))
    if must_keep:
        sections.append("Must-keep human phrasing where factually compatible: " + " | ".join(must_keep))
    if questions:
        sections.append("Open questions from the conversation: " + " | ".join(questions))
    if suspicions:
        sections.append("Human suspicions/hypotheses; investigate, do not assume: " + " | ".join(suspicions))
    if analogies:
        sections.append("Candidate historical analogies; use only if relevant and accurate: " + " | ".join(analogies))
    if claims:
        sections.append("Candidate factual claims that must be verified independently: " + " | ".join(claims))
    if supplied_urls:
        sections.append("User-supplied URLs to inspect as leads, not automatically trusted evidence: " + " | ".join(supplied_urls))
    if visuals:
        sections.append("Candidate visual ideas: " + " | ".join(visuals))
    if timing:
        sections.append("Timing/performance notes: " + timing)
    if avoid:
        sections.append("Avoid: " + " | ".join(avoid))
    sections.append("Write one coherent spoken story. Preserve strong human ideas and jokes when they survive factual review; do not concatenate notes as blocks.")

    return {
        "schema_version": 2,
        "topic": topic,
        "opening_strategy": opening,
        "model": model,
        "max_openai_usd": budget,
        "angle": "\n".join(sections),
        "creative_brief": {
            "core_thesis": thesis,
            "editorial_notes": notes,
            "candidate_lines": candidate,
            "must_keep_lines": must_keep,
            "open_questions": questions,
            "suspicions": suspicions,
            "historical_analogies": analogies,
            "visual_ideas": visuals,
            "claims_to_verify": claims,
            "supplied_urls": supplied_urls,
            "timing_notes": timing,
            "avoid": avoid,
            "host_mode": host_mode,
            "plate_r2_key": plate_r2_key,
            "plate_local_path": plate_local_path,
            "dialogue_avatar_id": dialogue_avatar_id,
            "dialogue_notes": dialogue_notes,
            "visual_mode": visual_mode,
        },
        "host_mode": host_mode,
        "plate_r2_key": plate_r2_key,
        "plate_local_path": plate_local_path,
        "dialogue_avatar_id": dialogue_avatar_id,
        "dialogue_notes": dialogue_notes,
        "visual_mode": visual_mode,
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
