# Reference corpus architecture

The Satoshi writer uses a reference corpus as an **editorial mechanics layer**.

It is deliberately separate from:
- the Satoshi persona (identity/voice);
- web research (facts/evidence);
- output format (short vs long form);
- visual direction.

## Private transcript-to-embedding pipeline

The repository now supports the direct path:

```text
private transcripts
→ deterministic paragraph-aware chunks
→ automatic rhetorical labeling
→ embedding
→ private SQLite index
→ semantic retrieval
```

Use `corpus_embeddings.py` for ingestion and retrieval. Raw transcript text and
embedding vectors are stored only in the SQLite database selected with `--db`.
Do not commit that database or the transcript directory to the public repo.

The default labeling model is `gpt-5.6-luna`, because labeling is a bounded,
high-volume classification task. The default embedding model is
`text-embedding-3-small`, currently shortened to 768 dimensions to reduce local
index size while retaining semantic retrieval capability. Both are configurable
through CLI flags or environment variables.

Example dry run:

```sh
python3 corpus_embeddings.py ingest \
  --transcript-dir /private/corpus/raw \
  --db /private/corpus/corpus.sqlite
```

Live indexing:

```sh
OPENAI_LIVE_ENABLED=true \
OPENAI_API_KEY=... \
python3 corpus_embeddings.py ingest \
  --transcript-dir /private/corpus/raw \
  --db /private/corpus/corpus.sqlite \
  --live
```

Semantic retrieval:

```sh
OPENAI_LIVE_ENABLED=true \
OPENAI_API_KEY=... \
python3 corpus_embeddings.py query \
  --db /private/corpus/corpus.sqlite \
  --text "counterintuitive fertility claim with evidence qualification" \
  --top-k 5 \
  --live
```

The index stores each chunk with source metadata, automatic rhetorical labels,
a retrieval string, embedding model/dimensions, and a float-vector BLOB. It
uses ordinary SQLite and brute-force dot-product ranking, which is sufficient
for hundreds or low-thousands of chunks. A dedicated vector database is not
needed at this scale.

## Why auto-label before embedding

Raw transcript embeddings are good at retrieving semantically similar subject
matter. The automatic label step adds rhetorical-function metadata such as
`hook`, `mechanism`, `evidence`, `reversal`, `qualification`, `callback`, and
`practical_implication`. This lets retrieval reflect both topic and storytelling
mechanics rather than topic alone.

## Public vs private corpus material

This public repository may contain:
- source URLs and provenance;
- corpus schemas and code;
- derived structural annotations;
- tests and evaluation rules.

It should not contain bulk third-party transcript text or the generated private
SQLite corpus. Rights to access a transcript are not the same as permission to
redistribute it.

## Evaluation

Embedding retrieval should still be treated as an experiment. The existing
static/tag-derived exemplar path remains a baseline. Promote semantic retrieval
into the canonical writer only after blinded evaluation shows better hooks,
coherence, evidence handling, originality, and audience fit.
