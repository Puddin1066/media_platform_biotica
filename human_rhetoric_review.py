"""Create and score a blind human review packet from a rhetoric benchmark.

The packet intentionally excludes arm labels and model-judge preferences. A separate
key file preserves the mapping so human judgments can be unblinded later.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


DIMENSIONS = ("keep_watching", "intelligent_not_generic", "biotica_fit")


def _stable_swap(brief_id: str) -> bool:
    return int(hashlib.sha256(("human-review:" + brief_id).encode()).hexdigest(), 16) % 2 == 0


def build_packet(benchmark: dict) -> tuple[dict, dict]:
    trials = benchmark.get("trials", [])
    if not trials:
        raise ValueError("Benchmark contains no trials")

    packet_trials = []
    key_trials = []
    for trial in trials:
        brief_id = trial["brief_id"]
        baseline = trial["baseline_script"]
        semantic = trial["semantic_script"]
        swap = _stable_swap(brief_id)
        if swap:
            a, b = semantic, baseline
            labels = {"A": "semantic", "B": "none"}
        else:
            a, b = baseline, semantic
            labels = {"A": "none", "B": "semantic"}

        packet_trials.append({
            "brief_id": brief_id,
            "topic": trial["topic"],
            "evidence": trial["evidence"],
            "candidate_A": a,
            "candidate_B": b,
        })
        key_trials.append({
            "brief_id": brief_id,
            "blind_order": labels,
            "model_judge": trial.get("judge"),
        })

    packet = {
        "schema_version": 1,
        "instructions": {
            "primary_choice": "Pick A, B, or tie based on which script you would actually publish.",
            "dimensions": {
                "keep_watching": "Which script makes you more likely to keep watching?",
                "intelligent_not_generic": "Which feels more intelligent/specific and less generic?",
                "biotica_fit": "Which better fits Satoshi Shkreli / Biotica Media?",
            },
            "blind": True,
        },
        "trials": packet_trials,
    }
    key = {
        "schema_version": 1,
        "benchmark_arms": benchmark.get("arms", ["none", "semantic"]),
        "trials": key_trials,
    }
    return packet, key


def packet_markdown(packet: dict) -> str:
    lines = [
        "# Blind Human Rhetoric Review",
        "",
        "For each pair, choose the script you would actually publish: **A**, **B**, or **tie**.",
        "Then optionally mark A/B/tie for three taste checks: keep watching, intelligent not generic, and Biotica fit.",
        "Do not try to infer which system produced either script.",
        "",
    ]
    for i, trial in enumerate(packet["trials"], 1):
        lines.extend([
            f"## Pair {i} — {trial['brief_id']}",
            "",
            f"**Topic:** {trial['topic']}",
            "",
            f"**Evidence brief:** {trial['evidence']}",
            "",
            "### Candidate A",
            trial["candidate_A"],
            "",
            "### Candidate B",
            trial["candidate_B"],
            "",
            "**Your choice:** A / B / tie",
            "",
            "**Keep watching:** A / B / tie  ",
            "**Intelligent, not generic:** A / B / tie  ",
            "**Biotica fit:** A / B / tie",
            "",
        ])
    return "\n".join(lines).rstrip() + "\n"


def write_response_template(packet: dict, path: Path) -> None:
    fieldnames = ["brief_id", "preferred", *DIMENSIONS, "notes"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for trial in packet["trials"]:
            writer.writerow({"brief_id": trial["brief_id"]})


def _validate_choice(value: str, field: str, brief_id: str, allow_blank: bool = False) -> str:
    value = (value or "").strip().lower()
    if allow_blank and not value:
        return ""
    if value not in {"a", "b", "tie"}:
        raise ValueError(f"{brief_id}: {field} must be A, B, or tie")
    return value.upper() if value in {"a", "b"} else "tie"


def score_responses(key: dict, responses_path: Path) -> dict:
    key_by_id = {row["brief_id"]: row for row in key["trials"]}
    with responses_path.open(encoding="utf-8", newline="") as f:
        responses = list(csv.DictReader(f))
    if not responses:
        raise ValueError("No human responses found")

    wins = {"none": 0, "semantic": 0, "tie": 0}
    model_agreement = {"agree": 0, "disagree": 0, "model_tie": 0, "human_tie": 0}
    scored = []
    for response in responses:
        brief_id = response.get("brief_id", "").strip()
        if brief_id not in key_by_id:
            raise ValueError(f"Unknown brief_id: {brief_id}")
        preferred = _validate_choice(response.get("preferred", ""), "preferred", brief_id)
        mapping = key_by_id[brief_id]["blind_order"]
        arm = "tie" if preferred == "tie" else mapping[preferred]
        wins[arm] += 1

        model_pref = (key_by_id[brief_id].get("model_judge") or {}).get("preferred")
        model_arm = "tie" if model_pref == "tie" else mapping.get(model_pref) if model_pref else None
        if preferred == "tie":
            model_agreement["human_tie"] += 1
        elif model_arm == "tie":
            model_agreement["model_tie"] += 1
        elif model_arm is not None:
            model_agreement["agree" if model_arm == arm else "disagree"] += 1

        dimensions = {
            d: _validate_choice(response.get(d, ""), d, brief_id, allow_blank=True)
            for d in DIMENSIONS
        }
        scored.append({
            "brief_id": brief_id,
            "human_blind_choice": preferred,
            "human_arm": arm,
            "model_arm": model_arm,
            "dimensions": dimensions,
            "notes": response.get("notes", ""),
        })

    decisive = wins["none"] + wins["semantic"]
    semantic_win_rate = wins["semantic"] / decisive if decisive else None
    return {
        "schema_version": 1,
        "human_wins": wins,
        "semantic_win_rate_excluding_ties": semantic_win_rate,
        "model_human_agreement": model_agreement,
        "trials": scored,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    make = sub.add_parser("make-packet")
    make.add_argument("--benchmark", required=True)
    make.add_argument("--output-dir", required=True)

    score = sub.add_parser("score")
    score.add_argument("--key", required=True)
    score.add_argument("--responses", required=True)
    score.add_argument("--output", required=True)

    args = p.parse_args()
    if args.command == "make-packet":
        benchmark = json.loads(Path(args.benchmark).read_text(encoding="utf-8"))
        packet, key = build_packet(benchmark)
        out = Path(args.output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "blind-review.json").write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        (out / "blind-review.md").write_text(packet_markdown(packet), encoding="utf-8")
        (out / "blind-key.json").write_text(json.dumps(key, indent=2) + "\n", encoding="utf-8")
        write_response_template(packet, out / "human-responses.csv")
        print(json.dumps({"pairs": len(packet["trials"]), "blind": True}, indent=2))
    else:
        key = json.loads(Path(args.key).read_text(encoding="utf-8"))
        result = score_responses(key, Path(args.responses))
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
