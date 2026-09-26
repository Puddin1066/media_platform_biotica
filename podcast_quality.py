"""Deterministic quality diagnostics and blinded comparison for podcast drafts."""
from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

RUBRIC = (
    "listening_pull",
    "naturalness",
    "coherence",
    "evidence_fidelity",
    "speaker_distinction",
    "originality",
)


def _tokens(text):
    return [t.lower() for t in re.findall(r"[A-Za-z0-9']+", text)]


def repetition_ratio(turns):
    """Fraction of adjacent turns with high lexical overlap."""
    if len(turns) < 2:
        return 0.0
    repeated = 0
    pairs = 0
    for a, b in zip(turns, turns[1:]):
        ta, tb = set(_tokens(a["text"])), set(_tokens(b["text"]))
        if not ta or not tb:
            continue
        pairs += 1
        score = len(ta & tb) / max(1, len(ta | tb))
        if score >= 0.45:
            repeated += 1
    return round(repeated / pairs, 3) if pairs else 0.0


def turn_length_cv(turns):
    lengths = [len(_tokens(t["text"])) for t in turns if _tokens(t["text"])]
    if len(lengths) < 2:
        return 0.0
    mean = sum(lengths) / len(lengths)
    if not mean:
        return 0.0
    variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
    return round(math.sqrt(variance) / mean, 3)


def agreement_streak(turns):
    """Simple heuristic for consecutive agreement-like openings."""
    pattern = re.compile(r"^(yes|exactly|right|absolutely|correct|totally|agreed)\b", re.I)
    streak = best = 0
    for turn in turns:
        if pattern.search(turn["text"].strip()):
            streak += 1
            best = max(best, streak)
        else:
            streak = 0
    return best


def function_distribution(turns):
    return dict(Counter(t["function"] for t in turns))


def speaker_distribution(turns):
    return dict(Counter(t["speaker"] for t in turns))


def unresolved_threads(state):
    opened = set(state.get("open_questions", []))
    resolved = set(state.get("resolved_questions", []))
    return sorted(opened - resolved)


def evidence_coverage(state):
    turns = state.get("turns", [])
    with_claims = sum(1 for t in turns if t.get("claim_ids"))
    with_sources = sum(1 for t in turns if t.get("source_ids"))
    total = len(turns) or 1
    return {
        "turns_with_claim_ids": with_claims,
        "turns_with_source_ids": with_sources,
        "claim_turn_ratio": round(with_claims / total, 3),
        "source_turn_ratio": round(with_sources / total, 3),
    }


def diagnose(state):
    turns = state.get("turns", [])
    if not isinstance(turns, list):
        raise ValueError("turns must be a list")
    functions = function_distribution(turns)
    warnings = []
    rep = repetition_ratio(turns)
    if rep > 0.25:
        warnings.append("high_adjacent_repetition")
    streak = agreement_streak(turns)
    if streak >= 3:
        warnings.append("excessive_agreement_streak")
    if functions.get("challenge", 0) + functions.get("reversal", 0) == 0 and len(turns) >= 8:
        warnings.append("no_challenge_or_reversal")
    if functions.get("callback", 0) == 0 and len(turns) >= 12:
        warnings.append("no_callback")
    if functions.get("resolution", 0) == 0 and state.get("status") == "review_required":
        warnings.append("no_resolution")
    return {
        "turns": len(turns),
        "speaker_distribution": speaker_distribution(turns),
        "function_distribution": functions,
        "repetition_ratio": rep,
        "turn_length_cv": turn_length_cv(turns),
        "max_agreement_streak": streak,
        "evidence_coverage": evidence_coverage(state),
        "unresolved_threads": unresolved_threads(state),
        "warnings": warnings,
    }


def validate_scorecard(card):
    if not isinstance(card, dict) or set(card) != {"pairs"}:
        raise ValueError("Expected pairs")
    if not isinstance(card["pairs"], list) or not card["pairs"]:
        raise ValueError("Need at least one pair")
    for pair in card["pairs"]:
        if set(pair) != {"id", "a", "b", "which_is_agentic"}:
            raise ValueError("Invalid pair fields")
        if pair["which_is_agentic"] not in ("a", "b"):
            raise ValueError("which_is_agentic must be a or b")
        for side in ("a", "b"):
            if set(pair[side]) != set(RUBRIC):
                raise ValueError("Each side needs full rubric")
            if any(not isinstance(v, (int, float)) or not 1 <= v <= 5
                   for v in pair[side].values()):
                raise ValueError("Rubric values must be 1-5")
    return card


def summarize_scorecard(card):
    validate_scorecard(card)
    arms = {"agentic": {k: [] for k in RUBRIC}, "baseline": {k: [] for k in RUBRIC}}
    for pair in card["pairs"]:
        agentic = pair["which_is_agentic"]
        baseline = "b" if agentic == "a" else "a"
        for key in RUBRIC:
            arms["agentic"][key].append(pair[agentic][key])
            arms["baseline"][key].append(pair[baseline][key])
    means = {
        arm: {k: round(sum(vals) / len(vals), 3) for k, vals in dims.items()}
        for arm, dims in arms.items()
    }
    deltas = {k: round(means["agentic"][k] - means["baseline"][k], 3) for k in RUBRIC}
    overall = round(sum(deltas.values()) / len(deltas), 3)
    return {
        "pairs": len(card["pairs"]),
        "means": means,
        "agentic_minus_baseline": deltas,
        "overall_delta": overall,
        "promotion_gate": {
            "eligible": overall > 0 and deltas["evidence_fidelity"] >= 0,
            "rule": (
                "Promote only if agentic writing improves overall blinded ratings "
                "and does not reduce evidence fidelity."
            ),
        },
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    d = sub.add_parser("diagnose")
    d.add_argument("--state", required=True)
    d.add_argument("--output")
    c = sub.add_parser("compare")
    c.add_argument("--scorecard", required=True)
    c.add_argument("--output")
    args = p.parse_args()

    if args.command == "diagnose":
        result = diagnose(json.loads(Path(args.state).read_text(encoding="utf-8")))
    else:
        result = summarize_scorecard(json.loads(Path(args.scorecard).read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
