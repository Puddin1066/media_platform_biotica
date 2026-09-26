# Reference corpus architecture

The Satoshi writer uses a reference corpus as an **editorial mechanics layer**.

It is deliberately separate from:
- the Satoshi persona (identity/voice);
- web research (facts/evidence);
- output format (short vs long form);
- visual direction.

## Canonical source: Huberman Lab solo episodes

The rhetoric system now uses a **single-source policy**. The canonical source is
Andrew Huberman's solo explanatory Huberman Lab episodes. Guest interviews,
advertisements, sponsor reads, housekeeping, intro/outro boilerplate, and
third-party speaker segments are excluded.

The purpose is not to imitate Huberman's voice or inject his prose into Satoshi.
The purpose is to learn neutral structural mechanics from a large, consistent,
health/science-focused body of one host's explanatory work.

The production separation is:

```text
Huberman solo episodes -> derived neutral mechanics -> retrieval
Satoshi persona canon  -----------------------------> writing voice
current web research   -----------------------------> episode facts/evidence
```

`rhetoric_source_policy.json` is the machine-readable contract. It requires:
- one canonical source family only;
- raw transcript text never enters production prompts;
- creator-specific phrasing never enters production prompts;
- no creator-voice imitation;
- facts come from current episode research, not the rhetoric corpus;
- Satoshi's persona remains a separate layer.

## Source selection and promotion

Start with 50–100 carefully selected solo episodes, with at least 25 distinct
validated episodes before any derived library can be considered production
ready. Overweight topics close to the intended audience (hormones, fertility,
sexual health, sleep, exercise, supplements, aging, body composition, stress,
motivation, and performance) while retaining some unrelated biology and
neuroscience episodes so retrieval learns explanatory method rather than topic
similarity alone.

Each promoted mechanic must have:
- `source_family: huberman_lab_solo`;
- one or more source episode IDs for provenance;
- a neutralized structural description;
- `contains_source_prose: false`.

The current `curated_mechanics.json` remains a **bootstrap-only** seed library.
It is not production canonical until entries are replaced or validated with
Huberman-solo provenance and the benchmark gate is passed.

## Benchmark before embedding

Do **not** treat bulk transcript embedding as the default enabling material.
The first question is whether derived mechanics improve Biotica output at all.

`rhetoric_benchmark.py` compares three blinded arms on the same men's-health
topic set:

1. `none` — no rhetoric retrieval;
2. `curated` — deterministic retrieval from neutralized mechanics;
3. `transcript` — experimental transcript-derived retrieval.

Score each candidate from 1–5 on hook strength, coherence, evidence handling,
originality, and audience fit. A retrieval strategy should become canonical only
if it beats no retrieval without degrading originality or evidence handling.
Embedding retrieval must then beat the simpler deterministic mechanics selector.

## Private transcript-to-embedding experiment

A transcript-derived experiment is still supported:

```text
private transcripts
-> deterministic paragraph-aware chunks
-> automatic rhetorical labeling
-> embedding
-> private SQLite index
-> semantic retrieval
```

Use `corpus_embeddings.py` for ingestion and retrieval. Raw transcript text and
embedding vectors stay only in the private SQLite database selected with `--db`.
Do not commit that database or transcript material to this public repo.

The default labeling model is `gpt-5.6-luna`. The default embedding model is
`text-embedding-3-small`, shortened to 768 dimensions. Both remain configurable.

Example dry run:

```sh
python3 corpus_embeddings.py ingest \
  --transcript-dir /private/corpus/raw \
  --db /private/corpus/corpus.sqlite
```

Live indexing requires private runtime credentials:

```sh
OPENAI_LIVE_ENABLED=true \
OPENAI_API_KEY=... \
python3 corpus_embeddings.py ingest \
  --transcript-dir /private/corpus/raw \
  --db /private/corpus/corpus.sqlite \
  --live
```

## Why derive before retrieval

Raw transcript embeddings tend to retrieve semantically similar subject matter.
That is not the production objective. We want reusable moves such as how to set
up a mechanism, qualify evidence, reconcile apparently conflicting studies, or
land a practical implication. The derivation step converts source material into
neutral structural representations so Satoshi receives craft guidance rather
than another creator's language.

## Public vs private corpus material

This public repository may contain:
- source URLs and episode identifiers;
- corpus schemas and code;
- derived structural annotations;
- original or neutralized abstract mechanics;
- tests and evaluation rules.

It should not contain bulk third-party transcript text or the generated private
SQLite corpus. Access to a transcript does not imply permission to redistribute
or reproduce it.

## Evaluation

Embedding retrieval is an experiment, not an assumption. The no-retrieval path
remains the baseline. Promote any retrieval strategy into the canonical writer
only after blinded evaluation shows a material improvement in hooks, coherence,
evidence handling, originality, and audience fit.
