"""Cluster neutralized rhetoric mechanics without embeddings.

This is a pre-embedding dedupe pass. It groups near-duplicate mechanics using
normalized token Jaccard similarity and preserves full provenance for every member.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

STOP = {
    "a","an","and","are","as","at","be","by","for","from","in","into","is","it",
    "of","on","or","that","the","then","to","use","when","with","without","you"
}
DEFAULT_THRESHOLD = 0.42


def tokens(text: str) -> set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) > 2 and w not in STOP
    }


def similarity(a: dict, b: dict) -> float:
    ta = tokens(f"{a['function']} {a['mechanic']}")
    tb = tokens(f"{b['function']} {b['mechanic']}")
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def load_mechanics(source_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(source_dir.glob("*.mechanics.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        episode_id = doc["episode_id"]
        for index, item in enumerate(doc["mechanics"]):
            rows.append({
                "episode_id": episode_id,
                "mechanic_index": index,
                **item,
            })
    return rows


def cluster(rows: list[dict], threshold: float = DEFAULT_THRESHOLD) -> list[dict]:
    clusters: list[dict] = []
    for row in rows:
        best_i = None
        best_score = 0.0
        for i, current in enumerate(clusters):
            score = similarity(row, current["representative"])
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= threshold:
            clusters[best_i]["members"].append(row)
            clusters[best_i]["max_member_similarity"] = max(
                clusters[best_i]["max_member_similarity"], round(best_score, 4)
            )
        else:
            clusters.append({
                "cluster_id": f"mechanic-{len(clusters)+1:03d}",
                "representative": row,
                "members": [row],
                "max_member_similarity": 1.0,
            })
    return clusters


def build_library(source_dir: Path, threshold: float = DEFAULT_THRESHOLD) -> dict:
    rows = load_mechanics(source_dir)
    clusters = cluster(rows, threshold)
    return {
        "schema_version": 1,
        "method": "deterministic_token_jaccard_pre_embedding",
        "similarity_threshold": threshold,
        "mechanic_count": len(rows),
        "cluster_count": len(clusters),
        "deduplicated_count": len(rows) - len(clusters),
        "clusters": clusters,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    args = p.parse_args()
    result = build_library(Path(args.source_dir), args.threshold)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("mechanic_count","cluster_count","deduplicated_count")}, indent=2))


if __name__ == "__main__":
    main()
