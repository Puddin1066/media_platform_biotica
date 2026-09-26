# Satoshi reference-corpus profile

## Purpose

The corpus teaches **writing mechanics**, not identity. Satoshi Shkreli remains
an original persona. Third-party examples may influence high-level structure,
evidence handling, pacing, and rhetorical functions, but must not be used to
reproduce another living creator's distinctive wording, catchphrases, or voice.

## Initial production hypothesis

Use one dominant corpus first: health/science explanatory material aligned with
the target audience. Huberman Lab is the initial source family because its
subject matter overlaps strongly with hormones, fertility, sexual health,
sleep, performance, diagnostics, and longevity.

Do not blend multiple creator personas by default. Secondary sources are
mechanics references only:

- argumentative/satirical mechanics: evidence receipt, escalation, callback;
- discovery mechanics: anomaly, delayed explanation, reframing.

## Raw vs derived material

This public repository stores:
- source URLs and provenance;
- derived structural annotations;
- topic/function labels;
- original summaries of why a passage works;
- optional vector IDs or embeddings later.

It does **not** store bulk third-party transcript text.

Authorized/private transcript files may be processed outside the repo to create
derived exemplar records.

## Exemplar schema

Each derived exemplar has:
- `mode`: argumentative or discovery;
- `functions`: hook/evidence/reveal/etc.;
- `summary`: original description of what the passage accomplishes;
- `mechanics`: original description of how it accomplishes it;
- `topic_tags`: retrieval tags;
- provenance via `source_id`.

## Retrieval sequence

Phase 1 uses deterministic tag retrieval. That creates a cheap baseline.

Phase 2 may add embeddings only after enough exemplars exist to justify dynamic
semantic retrieval. The embedding is a selector, not the persona and not the
writer.

The writer receives:

1. Satoshi persona;
2. target audience;
3. narrative mode;
4. 3-5 derived exemplar mechanics;
5. current research/evidence packet;
6. output schema and validators.

## Success criterion

Do not promote embedding retrieval merely because it is more sophisticated.
Promote it only if blinded/script-level evaluation shows better hooks,
coherence, evidence handling, originality, and audience fit than the simple
tag-retrieval baseline.
