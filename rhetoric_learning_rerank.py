"""Guarded performance reranking for rhetoric retrieval.

Semantic similarity remains authoritative until sufficient HUMAN-reviewed benchmark
history exists. Model-judge outcomes alone never change retrieval.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Callable

MIN_HUMAN_TRIALS = 12
MIN_MECHANIC_EXPOSURES = 3
PERFORMANCE_WEIGHT = 0.08
SHRINKAGE = 4.0


def load_human_priors(ledger_path: Path) -> dict:
    stats = defaultdict(lambda: {"exposures": 0, "wins": 0.0, "losses": 0.0, "ties": 0.0})
    reviewed = 0
    if not ledger_path.exists():
        return {"enabled": False, "human_trials": 0, "mechanics": {}}

    for raw in ledger_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        run = json.loads(raw)
        for trial in run.get("trials", []):
            choice = trial.get("human_choice")
            if choice not in {"semantic", "none", "tie"}:
                continue
            reviewed += 1
            for mechanic in trial.get("retrieved_mechanics", []):
                row = stats[mechanic["id"]]
                row["exposures"] += 1
                if choice == "semantic":
                    row["wins"] += 1.0
                elif choice == "none":
                    row["losses"] += 1.0
                else:
                    row["ties"] += 1.0

    mechanics = {}
    for mechanic_id, row in stats.items():
        # Shrunk signed effect in [-1, 1]. Repeated human wins/losses matter;
        # sparse observations stay close to zero.
        effect = (row["wins"] - row["losses"]) / (row["exposures"] + SHRINKAGE)
        mechanics[mechanic_id] = {**row, "effect": effect}

    return {
        "enabled": reviewed >= MIN_HUMAN_TRIALS,
        "human_trials": reviewed,
        "minimum_human_trials": MIN_HUMAN_TRIALS,
        "minimum_mechanic_exposures": MIN_MECHANIC_EXPOSURES,
        "performance_weight": PERFORMANCE_WEIGHT,
        "mechanics": mechanics,
    }


def rerank(rows: list[dict], priors: dict, top_k: int) -> list[dict]:
    if not priors.get("enabled"):
        return rows[:max(1, top_k)]

    rescored = []
    for row in rows:
        prior = priors.get("mechanics", {}).get(row["id"])
        effect = 0.0
        if prior and prior["exposures"] >= MIN_MECHANIC_EXPOSURES:
            effect = float(prior["effect"])
        updated = dict(row)
        updated["semantic_score"] = float(row["score"])
        updated["human_prior_effect"] = effect
        updated["score"] = updated["semantic_score"] + PERFORMANCE_WEIGHT * effect
        rescored.append(updated)
    rescored.sort(key=lambda row: row["score"], reverse=True)
    return rescored[:max(1, top_k)]


def wrap_retrieve(base_retrieve: Callable, ledger_path: Path) -> Callable:
    priors = load_human_priors(ledger_path)

    def learned_retrieve(index: dict, query: str, top_k: int = 6) -> list[dict]:
        # Ask semantic retrieval for the full library, then apply the guarded prior.
        rows = base_retrieve(index, query, top_k=len(index["items"]))
        return rerank(rows, priors, top_k)

    learned_retrieve.learning_state = priors
    return learned_retrieve
