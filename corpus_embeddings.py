"""Private transcript -> rhetorical labels -> embeddings -> SQLite retrieval.

Raw transcript text and vectors stay in a local/private SQLite database. This
public repository contains only the ingestion/retrieval code and schema.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sqlite3
import struct
import urllib.error
import urllib.request
from pathlib import Path

RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
EMBEDDINGS_ENDPOINT = "https://api.openai.com/v1/embeddings"
DEFAULT_LABEL_MODEL = os.environ.get("OPENAI_CORPUS_LABEL_MODEL", "gpt-5.6-luna")
DEFAULT_EMBED_MODEL = os.environ.get("OPENAI_EMBED_MODEL", "text-embedding-3-small")
DEFAULT_DIMENSIONS = int(os.environ.get("OPENAI_EMBED_DIMENSIONS", "768"))
FUNCTIONS = [
    "hook", "problem_setup", "mechanism", "evidence", "interpretation",
    "challenge", "clarification", "counterexample", "reversal",
    "qualification", "practical_implication", "analogy", "anecdote",
    "callback", "conclusion", "transition", "humor",
]
LABEL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["primary_function", "secondary_functions", "topic_tags", "mechanics", "audience_stakes"],
    "properties": {
        "primary_function": {"type": "string", "enum": FUNCTIONS},
        "secondary_functions": {"type": "array", "items": {"type": "string", "enum": FUNCTIONS}},
        "topic_tags": {"type": "array", "items": {"type": "string"}},
        "mechanics": {"type": "string"},
        "audience_stakes": {"type": "string"},
    },
}


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text, target_chars=2200, overlap_chars=300):
    """Paragraph-aware deterministic chunking without external tokenizer deps."""
    text = normalize_text(text)
    if not text:
        return []
    if target_chars < 500 or overlap_chars < 0 or overlap_chars >= target_chars:
        raise ValueError("Invalid chunk sizing")
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for paragraph in paragraphs:
        candidate = paragraph if not current else current + "\n\n" + paragraph
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            tail = current[-overlap_chars:] if overlap_chars else ""
            current = (tail + "\n\n" + paragraph).strip()
        else:
            start = 0
            while start < len(paragraph):
                end = min(len(paragraph), start + target_chars)
                chunks.append(paragraph[start:end])
                if end == len(paragraph):
                    current = ""
                    break
                start = max(start + 1, end - overlap_chars)
    if current:
        chunks.append(current)
    return chunks


def _openai_json(endpoint, body, key, timeout=120):
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            return json.loads(response.read(8_000_000))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError):
        raise RuntimeError("OpenAI corpus request failed or outcome is unknown") from None


def label_chunk(text, model, key):
    body = {
        "model": model,
        "store": False,
        "instructions": (
            "Analyze this transcript passage as writing craft, not factual authority. "
            "Classify its dominant rhetorical function and describe the transferable mechanics in original words. "
            "Do not quote or imitate distinctive phrasing. Keep mechanics concise and useful to a writing agent."
        ),
        "input": text,
        "max_output_tokens": 400,
        "text": {"format": {"type": "json_schema", "name": "rhetorical_label", "strict": True, "schema": LABEL_SCHEMA}},
    }
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    if result.get("status") != "completed":
        raise ValueError("Label response incomplete")
    out = "".join(
        p.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for p in item.get("content", []) if p.get("type") == "output_text"
    )
    if not out:
        raise ValueError("No label output")
    value = json.loads(out)
    if value.get("primary_function") not in FUNCTIONS:
        raise ValueError("Invalid rhetorical function")
    return value


def embed_texts(texts, model, dimensions, key):
    if not texts:
        return []
    body = {"model": model, "input": texts, "encoding_format": "float", "dimensions": dimensions}
    result = _openai_json(EMBEDDINGS_ENDPOINT, body, key)
    rows = sorted(result.get("data", []), key=lambda x: x.get("index", 0))
    if len(rows) != len(texts):
        raise ValueError("Embedding response length mismatch")
    vectors = [row.get("embedding") for row in rows]
    if any(not isinstance(v, list) or len(v) != dimensions for v in vectors):
        raise ValueError("Embedding dimensions mismatch")
    return vectors


def pack_vector(vector):
    return struct.pack("<%sf" % len(vector), *vector)


def unpack_vector(blob, dimensions):
    return struct.unpack("<%sf" % dimensions, blob)


def connect(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            source_path TEXT NOT NULL,
            source_title TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text_sha256 TEXT NOT NULL,
            text TEXT NOT NULL,
            labels_json TEXT NOT NULL,
            retrieval_text TEXT NOT NULL,
            embedding_model TEXT NOT NULL,
            embedding_dimensions INTEGER NOT NULL,
            embedding BLOB NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_path, chunk_index, text_sha256)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_source ON chunks(source_path)")
    db.commit()
    return db


def retrieval_text(chunk, labels):
    return "\n".join([
        "rhetorical function: " + labels["primary_function"],
        "secondary functions: " + ", ".join(labels["secondary_functions"]),
        "topics: " + ", ".join(labels["topic_tags"]),
        "audience stakes: " + labels["audience_stakes"],
        "mechanics: " + labels["mechanics"],
        "passage: " + chunk,
    ])


def ingest_file(db_path, transcript_path, source_title=None, label_model=DEFAULT_LABEL_MODEL,
                embed_model=DEFAULT_EMBED_MODEL, dimensions=DEFAULT_DIMENSIONS,
                target_chars=2200, overlap_chars=300, batch_size=32, live=False):
    path = Path(transcript_path)
    if not path.is_file():
        raise ValueError("Transcript file not found")
    if not live:
        return {"status": "dry_run", "file": str(path), "chunks": len(chunk_text(path.read_text(encoding="utf-8"), target_chars, overlap_chars)),
                "label_model": label_model, "embedding_model": embed_model, "dimensions": dimensions}
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing")
    chunks = chunk_text(path.read_text(encoding="utf-8"), target_chars, overlap_chars)
    title = source_title or path.stem
    rows = []
    for idx, chunk in enumerate(chunks):
        labels = label_chunk(chunk, label_model, key)
        rows.append((idx, chunk, labels, retrieval_text(chunk, labels)))
    vectors = []
    for start in range(0, len(rows), batch_size):
        vectors.extend(embed_texts([r[3] for r in rows[start:start + batch_size]], embed_model, dimensions, key))
    with connect(db_path) as db:
        inserted = 0
        for (idx, chunk, labels, rtext), vector in zip(rows, vectors):
            text_hash = sha256_text(chunk)
            chunk_id = sha256_text(str(path) + "\n" + str(idx) + "\n" + text_hash)
            cur = db.execute("""
                INSERT OR IGNORE INTO chunks
                (id, source_path, source_title, chunk_index, text_sha256, text, labels_json,
                 retrieval_text, embedding_model, embedding_dimensions, embedding)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (chunk_id, str(path), title, idx, text_hash, chunk,
                  json.dumps(labels, ensure_ascii=False), rtext, embed_model, dimensions, pack_vector(vector)))
            inserted += cur.rowcount
        db.commit()
    return {"status": "indexed", "file": str(path), "chunks": len(rows), "inserted": inserted,
            "label_model": label_model, "embedding_model": embed_model, "dimensions": dimensions}


def ingest_dir(db_path, transcript_dir, **kwargs):
    root = Path(transcript_dir)
    files = sorted([p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in {".txt", ".md"}])
    if not files:
        raise ValueError("No .txt or .md transcripts found")
    return [ingest_file(db_path, p, source_title=p.stem, **kwargs) for p in files]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def search(db_path, query, top_k=5, embed_model=DEFAULT_EMBED_MODEL,
           dimensions=DEFAULT_DIMENSIONS, live=False):
    if not live:
        return {"status": "dry_run", "query": query, "top_k": top_k,
                "embedding_model": embed_model, "dimensions": dimensions}
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ValueError("OPENAI_API_KEY missing")
    qvec = embed_texts([query], embed_model, dimensions, key)[0]
    scored = []
    with sqlite3.connect(db_path) as db:
        for row in db.execute("SELECT id, source_title, chunk_index, labels_json, retrieval_text, embedding FROM chunks WHERE embedding_model=? AND embedding_dimensions=?", (embed_model, dimensions)):
            cid, title, idx, labels, rtext, blob = row
            score = dot(qvec, unpack_vector(blob, dimensions))
            scored.append({"id": cid, "source_title": title, "chunk_index": idx,
                           "score": round(score, 6), "labels": json.loads(labels),
                           "retrieval_text": rtext})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"query": query, "results": scored[:max(1, top_k)]}


def stats(db_path):
    with sqlite3.connect(db_path) as db:
        total = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        sources = db.execute("SELECT COUNT(DISTINCT source_path) FROM chunks").fetchone()[0]
        models = db.execute("SELECT embedding_model, embedding_dimensions, COUNT(*) FROM chunks GROUP BY 1,2").fetchall()
    return {"chunks": total, "sources": sources,
            "indexes": [{"model": m, "dimensions": d, "chunks": n} for m, d, n in models]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("ingest")
    i.add_argument("--transcript-dir", required=True)
    i.add_argument("--db", required=True)
    i.add_argument("--label-model", default=DEFAULT_LABEL_MODEL)
    i.add_argument("--embedding-model", default=DEFAULT_EMBED_MODEL)
    i.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)
    i.add_argument("--target-chars", type=int, default=2200)
    i.add_argument("--overlap-chars", type=int, default=300)
    i.add_argument("--batch-size", type=int, default=32)
    i.add_argument("--live", action="store_true")
    q = sub.add_parser("query")
    q.add_argument("--db", required=True)
    q.add_argument("--text", required=True)
    q.add_argument("--top-k", type=int, default=5)
    q.add_argument("--embedding-model", default=DEFAULT_EMBED_MODEL)
    q.add_argument("--dimensions", type=int, default=DEFAULT_DIMENSIONS)
    q.add_argument("--live", action="store_true")
    s = sub.add_parser("stats")
    s.add_argument("--db", required=True)
    args = p.parse_args()
    if args.command == "ingest":
        result = ingest_dir(args.db, args.transcript_dir, label_model=args.label_model,
                            embed_model=args.embedding_model, dimensions=args.dimensions,
                            target_chars=args.target_chars, overlap_chars=args.overlap_chars,
                            batch_size=args.batch_size, live=args.live)
    elif args.command == "query":
        result = search(args.db, args.text, args.top_k, args.embedding_model, args.dimensions, args.live)
    else:
        result = stats(args.db)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
