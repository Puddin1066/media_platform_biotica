"""Evaluate whether rhetorical retrieval improves Biotica scripts.

This module deliberately does not make curated retrieval canonical. It defines
an offline benchmark contract for comparing three arms on the same topic set:
no retrieval, curated mechanics retrieval, and transcript-derived retrieval.
Promotion requires blinded scoring and a material win on quality dimensions.
"""
from __future__ import annotations

import json
from pathlib import Path

CURATED = Path(__file__).parent / "curated_mechanics.json"
ARMS = ("none", "curated", "transcript")
DIMENSIONS = (
    "hook_strength",
    "coherence",
    "evidence_handling",
    "originality",
    "audience_fit",
)


def load_curated(path=CURATED):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("entries"), list):
        raise ValueError("Invalid curated mechanics library")
    ids = set()
    for entry in data["entries"]:
        if not all(isinstance(entry.get(k), str) and entry[k].strip()
                   for k in ("id", "mode", "function", "mechanic")):
            raise ValueError("Each curated mechanic requires id, mode, function and mechanic")
        if entry["id"] in ids:
            raise ValueError("Duplicate curated mechanic id")
        ids.add(entry["id"])
        if not isinstance(entry.get("best_for"), list) or not isinstance(entry.get("avoid"), list):
            raise ValueError("Curated mechanic needs best_for and avoid lists")
    return data


def benchmark_manifest(topics):
    """Build deterministic blinded comparison slots for identical topics."""
    if not isinstance(topics, list) or not topics:
        raise ValueError("Benchmark requires at least one topic")
    rows = []
    for index, topic in enumerate(topics, 1):
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError("Benchmark topics must be non-empty strings")
        topic_id = f"T{index:03d}"
        for arm in ARMS:
            rows.append({
                "topic_id": topic_id,
                "topic": topic.strip(),
                "arm": arm,
                "candidate_id": f"{topic_id}-{arm}",
                "status": "awaiting_generation",
            })
    return {
        "schema_version": 1,
        "arms": list(ARMS),
        "dimensions": list(DIMENSIONS),
        "candidates": rows,
        "promotion_rule": {
            "required": "curated must beat no-retrieval without losing originality or evidence handling",
            "transcript_policy": "transcript retrieval stays experimental unless it independently beats curated retrieval",
        },
    }


def validate_scores(manifest, scores):
    candidates = {row["candidate_id"] for row in manifest["candidates"]}
    seen = set()
    for score in scores:
        cid = score.get("candidate_id")
        if cid not in candidates or cid in seen:
            raise ValueError("Unknown or duplicate candidate score")
        seen.add(cid)
        for dimension in DIMENSIONS:
            value = score.get(dimension)
            if not isinstance(value, (int, float)) or not 1 <= value <= 5:
                raise ValueError(f"{dimension} must be scored from 1 to 5")
    return True


def summarize(manifest, scores):
    validate_scores(manifest, scores)
    totals = {arm: {d: [] for d in DIMENSIONS} for arm in ARMS}
    by_candidate = {s["candidate_id"]: s for s in scores}
    for candidate in manifest["candidates"]:
        score = by_candidate.get(candidate["candidate_id"])
        if not score:
            continue
        for dimension in DIMENSIONS:
            totals[candidate["arm"]][dimension].append(float(score[dimension]))
    means = {}
    for arm, dims in totals.items():
        means[arm] = {
            d: (sum(values) / len(values) if values else None)
            for d, values in dims.items()
        }
    return means
