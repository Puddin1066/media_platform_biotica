"""Namespace and retrieval filters for the shared rhetorical embedding index.

All source families share one embedding model/vector space. Retrieval first
filters by explicit source_family and/or narrative mode, then ranks candidates
by vector similarity. This prevents accidental creator/style blending while
keeping one compact index.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3

import corpus_embeddings as ce

SOURCE_ALIASES = {
    "huberman": "huberman",
    "huberman-lab": "huberman",
    "huberman_lab": "huberman",
    "lwt": "lwt",
    "last-week-tonight": "lwt",
    "last_week_tonight": "lwt",
    "revisionist": "revisionist",
    "revisionist-history": "revisionist",
    "revisionist_history": "revisionist",
}

DEFAULT_MODE_BY_SOURCE = {
    "huberman": "explanatory",
    "lwt": "argumentative",
    "revisionist": "discovery",
}

ALLOWED_MODES = {"argumentative", "explanatory", "discovery"}


def normalize_source_family(value):
    value = str(value or "").strip().lower().replace(" ", "-")
    return SOURCE_ALIASES.get(value, value or "unknown")


def infer_source_family(source_path):
    """Infer family from first path segment: e.g. huberman/episode-1.txt."""
    path = str(source_path or "").replace("\\", "/").strip("/")
    first = path.split("/", 1)[0] if path else "unknown"
    return normalize_source_family(first)


def infer_mode(source_family):
    return DEFAULT_MODE_BY_SOURCE.get(normalize_source_family(source_family), "unknown")


def enrich_labels(labels, source_path, source_family=None, mode=None):
    out = dict(labels)
    family = normalize_source_family(source_family or infer_source_family(source_path))
    selected_mode = str(mode or infer_mode(family)).strip().lower()
    if selected_mode != "unknown" and selected_mode not in ALLOWED_MODES:
        raise ValueError("Unknown narrative mode")
    out["source_family"] = family
    out["mode"] = selected_mode
    return out


def metadata_from_row(source_path, labels):
    family = normalize_source_family(labels.get("source_family") or infer_source_family(source_path))
    mode = str(labels.get("mode") or infer_mode(family)).strip().lower()
    return family, mode


def search(db_path, query, top_k=5, source_family="", mode="",
           embed_model=ce.DEFAULT_EMBED_MODEL, dimensions=ce.DEFAULT_DIMENSIONS,
           live=False):
    family_filter = normalize_source_family(source_family) if source_family else ""
    mode_filter = str(mode or "").strip().lower()
    if mode_filter and mode_filter not in ALLOWED_MODES:
        raise ValueError("Unknown narrative mode")
    if not live:
        return {
            "status": "dry_run", "query": query, "top_k": top_k,
            "source_family": family_filter or None, "mode": mode_filter or None,
            "embedding_model": embed_model, "dimensions": dimensions,
        }
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing")
    qvec = ce.embed_texts([query], embed_model, dimensions, key)[0]
    scored = []
    with sqlite3.connect(db_path) as db:
        rows = db.execute(
            "SELECT id, source_path, source_title, chunk_index, labels_json, retrieval_text, embedding "
            "FROM chunks WHERE embedding_model=? AND embedding_dimensions=?",
            (embed_model, dimensions),
        )
        for cid, source_path, title, idx, labels_json, rtext, blob in rows:
            labels = json.loads(labels_json)
            family, row_mode = metadata_from_row(source_path, labels)
            if family_filter and family != family_filter:
                continue
            if mode_filter and row_mode != mode_filter:
                continue
            score = ce.dot(qvec, ce.unpack_vector(blob, dimensions))
            scored.append({
                "id": cid, "source_title": title, "chunk_index": idx,
                "source_family": family, "mode": row_mode,
                "score": round(score, 6), "labels": labels,
                "retrieval_text": rtext,
            })
    scored.sort(key=lambda row: row["score"], reverse=True)
    return {
        "query": query,
        "source_family": family_filter or None,
        "mode": mode_filter or None,
        "results": scored[:max(1, int(top_k))],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", required=True)
    p.add_argument("--text", required=True)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--source-family", default="")
    p.add_argument("--mode", default="")
    p.add_argument("--embedding-model", default=ce.DEFAULT_EMBED_MODEL)
    p.add_argument("--dimensions", type=int, default=ce.DEFAULT_DIMENSIONS)
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    result = search(args.db, args.text, args.top_k, args.source_family, args.mode,
                    args.embedding_model, args.dimensions, args.live)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
