# Reference corpus architecture

The Satoshi writer uses a reference corpus as an **editorial mechanics layer**.

It is deliberately separate from:
- the Satoshi persona (identity/voice);
- web research (facts/evidence);
- output format (short vs long form);
- visual direction.

The initial implementation avoids embeddings. It loads derived exemplars and
selects them with deterministic topic-tag overlap. This is intentionally simple:
we need evidence that examples improve scripts before adding vector retrieval.

Future embedding retrieval can use an existing embedding model to represent
derived exemplar summaries/mechanics and the current story need as vectors,
then retrieve the nearest 3-5 examples. No custom embedding model is required.

Raw third-party transcripts are not committed to this public repository.
