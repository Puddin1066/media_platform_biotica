"""Semantic retrieval of neutral rhetoric mechanics for Satoshi writing.

The private embedding index may contain raw transcript text, but this module never
returns it to production prompts. Only neutral labels/mechanics and provenance are
returned. If no private index is configured, callers fall back to the public,
deterministic exemplar selector.
"""
from __future__ import annotations

import os
from pathlib import Path

import corpus_embeddings


def enabled():
    return os.environ.get("SATOSHI_EMBED_RETRIEVAL_ENABLED", "true").lower() != "false"


def query_text(case, mode):
    canon = case.get("canon", {})
    requested_angle = canon.get("requested_angle", "") if isinstance(canon, dict) else ""
    return "\n".join([
        f"narrative mode: {mode}",
        f"question: {case.get('question', '')}",
        f"editorial angle: {requested_angle}",
        "retrieve transferable explanatory mechanics, not topical facts or creator phrasing",
    ])


def semantic_mechanics(case, mode, limit=3):
    if not enabled():
        return []
    db = os.environ.get("SATOSHI_CORPUS_DB", "").strip()
    if not db or not Path(db).is_file():
        return []
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true" or not os.environ.get("OPENAI_API_KEY"):
        return []

    result = corpus_embeddings.search(db, query_text(case, mode), top_k=limit, live=True)
    output = []
    for row in result.get("results", []):
        labels = row.get("labels") or {}
        mechanics = str(labels.get("mechanics", "")).strip()
        if not mechanics:
            continue
        functions = [labels.get("primary_function")]
        functions.extend(labels.get("secondary_functions") or [])
        functions = [str(x) for x in functions if x]
        output.append({
            "id": "huberman-embedding:" + str(row.get("id", ""))[:16],
            "mode": mode,
            "functions": functions,
            "summary": str(labels.get("audience_stakes", "")).strip(),
            "mechanics": mechanics,
            "provenance": {
                "source_title": row.get("source_title", ""),
                "chunk_index": row.get("chunk_index"),
                "similarity": row.get("score"),
                "retrieval": "private_embedding",
            },
        })
    return output
