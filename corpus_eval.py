"""Compare blinded baseline vs corpus-conditioned script ratings.

This does not judge scripts automatically. It aggregates reviewer scores so the
team can decide whether corpus conditioning earns more complexity.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DIMENSIONS = ("hook", "coherence", "evidence_handling", "originality", "audience_fit")


def validate_scorecard(card):
    if not isinstance(card, dict) or set(card) != {"pairs"}:
        raise ValueError("Expected pairs only")
    pairs = card["pairs"]
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("Need at least one pair")
    for pair in pairs:
        if set(pair) != {"id", "a", "b", "which_is_conditioned"}:
            raise ValueError("Invalid pair fields")
        if pair["which_is_conditioned"] not in ("a", "b"):
            raise ValueError("which_is_conditioned must be a or b")
        for side in ("a", "b"):
            scores = pair[side]
            if set(scores) != set(DIMENSIONS):
                raise ValueError("Each side needs all rubric dimensions")
            for value in scores.values():
                if not isinstance(value, (int, float)) or not 1 <= value <= 5:
                    raise ValueError("Scores must be 1-5")
    return card


def summarize(card):
    validate_scorecard(card)
    totals = {
        "baseline": {d: [] for d in DIMENSIONS},
        "conditioned": {d: [] for d in DIMENSIONS},
    }
    for pair in card["pairs"]:
        conditioned = pair["which_is_conditioned"]
        baseline = "b" if conditioned == "a" else "a"
        for d in DIMENSIONS:
            totals["conditioned"][d].append(pair[conditioned][d])
            totals["baseline"][d].append(pair[baseline][d])

    means = {
        arm: {d: round(sum(vals) / len(vals), 3) for d, vals in dims.items()}
        for arm, dims in totals.items()
    }
    deltas = {d: round(means["conditioned"][d] - means["baseline"][d], 3)
              for d in DIMENSIONS}
    average_delta = round(sum(deltas.values()) / len(deltas), 3)
    return {
        "pairs": len(card["pairs"]),
        "means": means,
        "conditioned_minus_baseline": deltas,
        "average_delta": average_delta,
        "embedding_gate": {
            "eligible_to_test_embeddings": average_delta > 0,
            "rule": (
                "Only test embedding retrieval after corpus conditioning beats the "
                "unconditioned baseline overall; embedding retrieval must then beat "
                "the deterministic corpus selector."
            ),
        },
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--scorecard", required=True)
    p.add_argument("--output")
    args = p.parse_args()
    result = summarize(json.loads(Path(args.scorecard).read_text(encoding="utf-8")))
    text = json.dumps(result, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
