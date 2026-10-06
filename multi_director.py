"""Deterministic multi-director selection for Satoshi candidate assets.

Three editorial agents score the same candidate library from different goals:
retention, credibility/clarity and comedy. A critic then builds a consensus cut
and flags beats that genuinely merit a paid regeneration.

This is a deterministic baseline contract. An LLM can later replace or augment
scores while preserving the same input/output schema.
"""
from __future__ import annotations

from typing import Any

import asset_coverage


DIRECTOR_WEIGHTS = {
    "retention": {
        "generated_motion": 5.0, "generated_still": 2.5, "remotion_native": 1.5, "evidence": 2.0,
        "retention": 2.0, "motion": 2.0, "comedy": 0.8, "credibility": 0.3,
    },
    "credibility": {
        "evidence": 5.0, "remotion_native": 3.0, "generated_still": 1.2, "generated_motion": 0.8,
        "credibility": 2.0, "clarity": 1.6, "receipt": 2.0, "cheap": 0.4,
    },
    "comedy": {
        "generated_motion": 4.0, "generated_still": 3.0, "remotion_native": 1.8, "evidence": 0.7,
        "comedy": 2.3, "illustration": 1.2, "retention": 0.8,
    },
}


def _score(candidate: dict[str, Any], director: str) -> float:
    weights = DIRECTOR_WEIGHTS[director]
    score = weights.get(candidate["candidate_type"], 0.0)
    for tag in candidate.get("selection_tags") or []:
        score += weights.get(tag, 0.0)

    # Evidence cannot win when unavailable; illustrative assets should not be
    # mistaken for proof by the credibility director.
    if candidate["candidate_type"] == "evidence" and candidate["factual_status"] != "requires_source_asset":
        return -999.0
    if director == "credibility" and candidate["factual_status"] == "illustration":
        score -= 0.7

    # Small cost penalty prevents directors from choosing motion by reflex.
    score -= 0.015 * float(candidate.get("estimated_runway_credits", 0))
    return round(score, 3)


def direct(library: dict[str, Any], director: str) -> dict[str, Any]:
    asset_coverage.validate_library(library)
    if director not in DIRECTOR_WEIGHTS:
        raise ValueError("unknown director")
    rows = library["candidates"]
    selected = []
    for slot_key, ids in library["by_slot"].items():
        options = [row for row in rows if row["asset_id"] in ids]
        ranked = sorted(options, key=lambda row: (_score(row, director), row["asset_id"]), reverse=True)
        winner = ranked[0]
        selected.append({
            "slot_key": slot_key,
            "cue_id": winner["cue_id"],
            "asset_id": winner["asset_id"],
            "score": _score(winner, director),
            "candidate_type": winner["candidate_type"],
            "reason": f'{director} director preferred {winner["candidate_type"]}',
            "alternates": [
                {"asset_id": row["asset_id"], "score": _score(row, director)}
                for row in ranked[1:3]
            ],
        })
    return {
        "schema_version": 1,
        "director": director,
        "status": "edit_candidate_ready",
        "selected": selected,
    }


def critic(library: dict[str, Any], edits: list[dict[str, Any]]) -> dict[str, Any]:
    """Choose a consensus cut and identify weak beats without provider calls."""
    asset_coverage.validate_library(library)
    directors = {edit.get("director"): edit for edit in edits}
    if set(directors) != set(DIRECTOR_WEIGHTS):
        raise ValueError("critic requires retention, credibility and comedy edits")

    by_asset = {row["asset_id"]: row for row in library["candidates"]}
    consensus = []
    regeneration = []

    slots = list(library["by_slot"])
    for slot_key in slots:
        votes: dict[str, int] = {}
        director_choices = {}
        for name, edit in directors.items():
            choice = next(row for row in edit["selected"] if row["slot_key"] == slot_key)
            asset_id = choice["asset_id"]
            director_choices[name] = asset_id
            votes[asset_id] = votes.get(asset_id, 0) + 1

        best_asset, best_votes = sorted(votes.items(), key=lambda item: (item[1], item[0]), reverse=True)[0]
        if best_votes == 1:
            # Tie: prefer credibility's choice unless it is missing.
            best_asset = director_choices["credibility"]

        chosen = by_asset[best_asset]
        consensus.append({
            "slot_key": slot_key,
            "cue_id": chosen["cue_id"],
            "asset_id": best_asset,
            "candidate_type": chosen["candidate_type"],
            "director_choices": director_choices,
            "consensus_votes": best_votes,
            "remotion_treatment": chosen["remotion_treatment"],
        })

        # A paid retry is justified only if no director selected either evidence
        # or a native treatment and there is no motion candidate available.
        cue_assets = [by_asset[asset_id] for asset_id in library["by_slot"][slot_key]]
        has_motion = any(row["candidate_type"] == "generated_motion" for row in cue_assets)
        all_illustrative = all(row["candidate_type"] == "generated_still" for row in
                               [by_asset[x] for x in set(director_choices.values())])
        if all_illustrative and not has_motion:
            regeneration.append({
                "slot_key": slot_key,
            "cue_id": chosen["cue_id"],
                "request": "consider one motion candidate only if preview pacing is weak",
                "max_incremental_runway_credits": 20,
            })

    return {
        "schema_version": 1,
        "status": "selected_edit_ready",
        "directors": sorted(directors),
        "selected_edit": consensus,
        "regeneration_requests": regeneration,
        "policy": "regenerate only a specifically weak beat; never rerender the episode wholesale",
    }


def tournament(library: dict[str, Any]) -> dict[str, Any]:
    edits = [direct(library, name) for name in DIRECTOR_WEIGHTS]
    return {
        "edits": edits,
        "critic": critic(library, edits),
    }
