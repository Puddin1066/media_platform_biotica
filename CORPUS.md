# Reference corpus architecture

The Satoshi writer uses a reference corpus as an **editorial mechanics layer**.

It is deliberately separate from:
- the Satoshi persona (identity/voice);
- web research (facts/evidence);
- output format (short vs long form);
- visual direction.

## Canonical experiment: curated mechanics first

Do **not** treat bulk transcript embedding as the default enabling material.
The first-class experiment is `curated_mechanics.json`: a small, original set
of abstract narrative mechanics such as claim -> receipt -> limitation,
steelmanning a counter-case, or separating documented incentives from evidence
of coordination. These entries describe transferable structures, not another
creator's wording or factual content.

The promotion question is simple: does retrieval of these mechanics improve a
Biotica script enough to justify the added retrieval layer?

`rhetoric_benchmark.py` defines three blinded comparison arms on the same topic
set:

1. `none` — no rhetoric retrieval;
2. `curated` — retrieval from the curated mechanics library;
3. `transcript` — experimental transcript-derived retrieval.

Score each candidate from 1–5 on hook strength, coherence, evidence handling,
originality, and audience fit. Curated retrieval should become canonical only if
it beats no retrieval without degrading originality or evidence handling.
Transcript retrieval should remain experimental unless it independently beats
the curated approach.

Start with roughly 20–30 representative men's-health topics and expand the
curated library only when a missing narrative function is identified. A useful
library is expected to stay small (roughly 50–150 high-value mechanics), not grow
because more transcript material is available.

## Private transcript-to-embedding pipeline

A transcript-derived experiment is still supported:

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
mechanics rather than topic alone. It does not solve the quality problem by
itself, which is why transcript retrieval remains a benchmark arm rather than
the default writer input.

## Public vs private corpus material

This public repository may contain:
- source URLs and provenance;
- corpus schemas and code;
- derived structural annotations;
- original abstract mechanics;
- tests and evaluation rules.

It should not contain bulk third-party transcript text or the generated private
SQLite corpus. Rights to access a transcript are not the same as permission to
redistribute it.

## Evaluation

Embedding retrieval is an experiment, not an assumption. The no-retrieval path
remains the baseline. Promote any retrieval strategy into the canonical writer
only after blinded evaluation shows a material improvement in hooks, coherence,
evidence handling, originality, and audience fit.
