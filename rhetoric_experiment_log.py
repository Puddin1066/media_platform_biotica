"""Append compact benchmark outcomes to a durable JSONL learning ledger."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def compact_trial(trial: dict) -> dict:
    judge = trial.get("judge", {})
    labels = trial.get("blind_order", {})
    preferred = judge.get("preferred")
    winner = "tie" if preferred == "tie" else labels.get(preferred)
    return {
        "brief_id": trial.get("brief_id"),
        "topic": trial.get("topic"),
        "retrieved_mechanics": [
            {
                "id": m.get("id"),
                "episode_id": m.get("episode_id"),
                "function": m.get("function"),
                "score": m.get("score"),
            }
            for m in trial.get("retrieved", [])
        ],
        "winner": winner,
        "publishable": {
            "none": _publishable_for_arm(judge, labels, "none"),
            "semantic": _publishable_for_arm(judge, labels, "semantic"),
        },
        "scores": {
            arm: _scores_for_arm(judge, labels, arm)
            for arm in ("none", "semantic")
        },
        "human_choice": None,
        "human_publishable": None,
    }


def _blind_for_arm(labels: dict, arm: str) -> str | None:
    for blind, label in labels.items():
        if label == arm:
            return blind
    return None


def _publishable_for_arm(judge: dict, labels: dict, arm: str):
    blind = _blind_for_arm(labels, arm)
    return judge.get(f"publishable_{blind}") if blind else None


def _scores_for_arm(judge: dict, labels: dict, arm: str) -> dict:
    blind = _blind_for_arm(labels, arm)
    value = judge.get(blind, {}) if blind else {}
    return value if isinstance(value, dict) else {}


def append_record(benchmark_path: Path, ledger_path: Path, run_id: str | None = None, commit_sha: str | None = None) -> dict:
    benchmark = json.loads(benchmark_path.read_text(encoding="utf-8"))
    record = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "commit_sha": commit_sha,
        "benchmark_target": benchmark.get("benchmark_target"),
        "top_k": benchmark.get("top_k"),
        "overall": benchmark.get("overall"),
        "semantic_delta": benchmark.get("semantic_delta"),
        "wins": benchmark.get("wins"),
        "publishable_counts": benchmark.get("publishable_counts"),
        "trials": [compact_trial(t) for t in benchmark.get("trials", [])],
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, separators=(",", ":")) + "\n")
    return record


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--benchmark", required=True)
    p.add_argument("--ledger", required=True)
    p.add_argument("--run-id")
    p.add_argument("--commit-sha")
    args = p.parse_args()
    record = append_record(Path(args.benchmark), Path(args.ledger), args.run_id, args.commit_sha)
    print(json.dumps({
        "logged_trials": len(record["trials"]),
        "semantic_delta": record["semantic_delta"],
        "wins": record["wins"],
    }, indent=2))


if __name__ == "__main__":
    main()
