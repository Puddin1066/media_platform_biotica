"""Incremental GitHub Actions builder for the private rhetorical corpus.

Source transcripts are read only during the build. The persisted runtime SQLite
index stores hashes, provenance, derived rhetorical metadata and embeddings, but
not bulk transcript text or quoted transcript passages.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

import corpus_embeddings as ce
import corpus_namespace as cn


def safe_retrieval_text(labels):
    return "\n".join([
        "source family: " + labels.get("source_family", "unknown"),
        "narrative mode: " + labels.get("mode", "unknown"),
        "rhetorical function: " + labels["primary_function"],
        "secondary functions: " + ", ".join(labels["secondary_functions"]),
        "topics: " + ", ".join(labels["topic_tags"]),
        "audience stakes: " + labels["audience_stakes"],
        "mechanics: " + labels["mechanics"],
    ])


def discover(root):
    root = Path(root)
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md"})


def build_plan(transcript_dir, db_path, embed_model, dimensions, target_chars=2200,
               overlap_chars=300, max_chunks=5000):
    root = Path(transcript_dir)
    files = discover(root)
    if not files:
        raise ValueError("No .txt or .md transcripts found")
    known = set()
    if Path(db_path).exists():
        with sqlite3.connect(db_path) as db:
            try:
                known = {row[0] for row in db.execute(
                    "SELECT id FROM chunks WHERE embedding_model=? AND embedding_dimensions=?",
                    (embed_model, dimensions),
                )}
            except sqlite3.OperationalError:
                known = set()
    rows = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        family = cn.infer_source_family(rel)
        mode = cn.infer_mode(family)
        for idx, chunk in enumerate(ce.chunk_text(path.read_text(encoding="utf-8"), target_chars, overlap_chars)):
            text_hash = ce.sha256_text(chunk)
            chunk_id = ce.sha256_text(rel + "\n" + str(idx) + "\n" + text_hash)
            rows.append({
                "id": chunk_id,
                "source_path": rel,
                "source_title": path.stem,
                "source_family": family,
                "mode": mode,
                "chunk_index": idx,
                "text_sha256": text_hash,
                "chunk": chunk,
            })
            if len(rows) >= max_chunks:
                break
        if len(rows) >= max_chunks:
            break
    pending = [row for row in rows if row["id"] not in known]
    counts = {}
    for row in rows:
        key = f'{row["source_family"]}:{row["mode"]}'
        counts[key] = counts.get(key, 0) + 1
    return {
        "files": len(files),
        "planned_chunks": len(rows),
        "already_indexed": len(rows) - len(pending),
        "namespace_counts": counts,
        "pending": pending,
    }


def build(transcript_dir, db_path, label_model=ce.DEFAULT_LABEL_MODEL,
          embed_model=ce.DEFAULT_EMBED_MODEL, dimensions=ce.DEFAULT_DIMENSIONS,
          target_chars=2200, overlap_chars=300, batch_size=32, max_chunks=5000,
          live=False):
    plan = build_plan(transcript_dir, db_path, embed_model, dimensions, target_chars,
                      overlap_chars, max_chunks)
    summary = {k: v for k, v in plan.items() if k != "pending"}
    summary.update({"pending_chunks": len(plan["pending"]), "label_model": label_model,
                    "embedding_model": embed_model, "dimensions": dimensions,
                    "live": bool(live)})
    if not live:
        summary["status"] = "dry_run"
        return summary
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing")

    enriched = []
    for row in plan["pending"]:
        labels = ce.label_chunk(row["chunk"], label_model, key)
        labels = cn.enrich_labels(labels, row["source_path"], row["source_family"], row["mode"])
        safe_text = safe_retrieval_text(labels)
        # Use source passage to place the vector, but never persist that passage.
        embed_input = safe_text + "\nsource passage:\n" + row["chunk"]
        enriched.append((row, labels, safe_text, embed_input))

    vectors = []
    for start in range(0, len(enriched), batch_size):
        vectors.extend(ce.embed_texts(
            [item[3] for item in enriched[start:start + batch_size]],
            embed_model, dimensions, key,
        ))

    with ce.connect(db_path) as db:
        inserted = 0
        for (row, labels, safe_text, _), vector in zip(enriched, vectors):
            cur = db.execute("""
                INSERT OR IGNORE INTO chunks
                (id, source_path, source_title, chunk_index, text_sha256, text, labels_json,
                 retrieval_text, embedding_model, embedding_dimensions, embedding)
                VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?)
            """, (row["id"], row["source_path"], row["source_title"], row["chunk_index"],
                  row["text_sha256"], json.dumps(labels, ensure_ascii=False), safe_text,
                  embed_model, dimensions, ce.pack_vector(vector)))
            inserted += cur.rowcount
        db.commit()
    summary.update({"status": "indexed", "inserted": inserted,
                    "final": ce.stats(db_path)})
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--transcript-dir", required=True)
    p.add_argument("--db", required=True)
    p.add_argument("--label-model", default=ce.DEFAULT_LABEL_MODEL)
    p.add_argument("--embedding-model", default=ce.DEFAULT_EMBED_MODEL)
    p.add_argument("--dimensions", type=int, default=ce.DEFAULT_DIMENSIONS)
    p.add_argument("--target-chars", type=int, default=2200)
    p.add_argument("--overlap-chars", type=int, default=300)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--max-chunks", type=int, default=5000)
    p.add_argument("--live", action="store_true")
    p.add_argument("--summary", default="")
    args = p.parse_args()
    result = build(args.transcript_dir, args.db, args.label_model, args.embedding_model,
                   args.dimensions, args.target_chars, args.overlap_chars,
                   args.batch_size, args.max_chunks, args.live)
    text = json.dumps(result, indent=2) + "\n"
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
