# Singular Satoshi Shorts Pipeline

Status: implementation specification

## Objective

One conversation should be enough to create one reliable short. The user discusses a topic, makes jokes, proposes analogies, challenges claims, and may supply URLs. That conversation is converted into one structured creative brief, enriched by evidence and rhetorical mechanics, written in the Satoshi persona, converted to one canonical narration, synchronized to host and graphics, rendered, checked, persisted to R2, and only then made eligible for Instagram publication.

The user-facing contract is:

```text
conversation
-> structured creative brief
-> claim extraction and web evidence enrichment
-> Huberman-derived rhetorical retrieval
-> Satoshi synthesis
-> locked script
-> canonical narration + timing
-> speech-driven host
-> deterministic graphics
-> render + sync/audio QC
-> R2 canonical asset
-> review
-> Instagram publish
```

No stage may silently substitute a different topic, script, voice, narration, or evidence source.

## 1. Conversation is the canonical creative input

`chat_request.py` becomes the normalization boundary between the conversation and the production system.

The request object should preserve structured fields instead of flattening everything into one angle string:

```json
{
  "topic": "...",
  "core_thesis": "...",
  "open_questions": ["..."],
  "suspicions": ["..."],
  "candidate_jokes": ["..."],
  "candidate_lines": ["..."],
  "must_keep_lines": ["..."],
  "historical_analogies": ["..."],
  "visual_ideas": ["..."],
  "claims_to_verify": ["..."],
  "supplied_urls": ["..."],
  "timing_notes": "...",
  "avoid": ["..."]
}
```

Rules:
- Human jokes, opinions and suspicions are creative material, not evidence.
- A human line containing a factual assertion is split into creative wording plus a claim requiring support.
- User-supplied URLs are research leads until validated.
- Must-keep phrasing is preserved when factually compatible; unsupported embedded facts are corrected without discarding the intended voice.

The normalized brief receives a `creative_brief_hash` and is immutable for a given run.

## 2. Claim extraction and evidence enrichment

The writer must not perform broad topic research only. It first extracts discrete factual claims from the structured brief and research hypotheses.

Each claim gets an evidence record:

```json
{
  "claim_id": "claim-...",
  "claim": "...",
  "status": "supported|contradicted|uncertain",
  "best_source_url": "https://...",
  "source_type": "primary_literature|registry|government|label|company|secondary",
  "supporting_urls": ["..."],
  "qualification": "...",
  "confidence": "high|moderate|low"
}
```

Research policy:
- Prefer primary literature, registries, regulators, labels and original documents.
- Search for contrary as well as supporting evidence.
- Every factual statement that survives into the spoken script must map to one or more evidence records.
- Jokes do not need citations unless they contain an embedded factual claim.
- Historical analogies involving real companies or people must be fact checked and framed precisely.

The evidence bundle receives an `evidence_hash`.

## 3. Huberman corpus is a rhetoric engine, not an evidence source

The Huberman corpus supplies transferable explanatory mechanics only.

Production retrieval should query the private embedding index using the whole structured brief plus rhetorical needs, for example:

```text
controversial intervention; major trial changes risk perception; explain noninferiority;
pivot to fertility tradeoff; preserve skepticism; land a practical unresolved choice
```

The semantic retrieval layer returns only neutralized mechanics and provenance:

```json
{
  "mechanic_id": "...",
  "primary_function": "mechanism",
  "secondary_functions": ["qualification", "reversal"],
  "mechanics": "...",
  "audience_stakes": "...",
  "source_episode_id": "...",
  "similarity_score": 0.0
}
```

Rules:
- Raw Huberman transcript text never enters the writing prompt.
- Huberman-derived text never serves as factual authority.
- Creator-specific wording, jokes, catchphrases or voice imitation are prohibited.
- Retrieval should return 3-5 mechanics maximum.
- If the private embedding index is unavailable, fall back deterministically to `reference_corpus.select_exemplars()`.
- The retrieval mode and selected mechanic IDs are recorded in the run manifest.

The rhetoric bundle receives a `rhetoric_hash`.

## 4. Satoshi persona is a separate writing layer

The Satoshi persona contract supplies worldview and voice, not evidence or rhetoric-source wording.

Default reasoning pattern:

```text
claim -> incentive -> historical precedent -> receipt -> cynical joke -> actual evidence -> provisional conclusion
```

The writer receives four explicitly separated inputs:

```text
HUMAN_INPUT
EVIDENCE
RHETORIC_MECHANICS
SATOSHI_PERSONA
```

The writer must preserve provenance rather than blending these inputs invisibly.

## 5. Script model and script contract

Script research/synthesis uses `gpt-5.6-sol` or the explicitly configured successor production-writing model.

The script output contains five ordered beats and segment-level provenance:

```json
{
  "beat": "evidence",
  "text": "...",
  "human_input_ids": ["human-2"],
  "claim_ids": ["claim-3"],
  "rhetoric_mechanic_ids": ["mechanic-17"],
  "persona_moves": ["incentive_analysis", "cynical_turn"],
  "source_urls": ["https://..."]
}
```

Acceptance requirements:
- One coherent spoken story, not concatenated research notes.
- Human jokes and observations are retained when they improve the piece.
- Every factual spoken claim has source provenance.
- Scientific uncertainty stays explicit.
- Historical analogies are relevant, concise and factually supportable.
- Persona is recognizable but does not overwhelm the evidence.

The approved script receives a `script_hash`. Any spoken-word change creates a new script hash and invalidates narration, host performance, timing and dependent graphics.

## 6. Canonical narration provider

Narration becomes its own deterministic provider stage. It must not be generated independently by the host-video provider.

Target provider: ElevenLabs through a dedicated `speech_provider` adapter, because the production requirement is high-quality speech plus machine-readable timing/alignment. The provider remains configurable behind the adapter.

The narration stage takes only the locked spoken script and configured voice profile.

Production normalization occurs before TTS:
- numbers are expanded to intended spoken form;
- acronyms receive explicit pronunciation where needed;
- ambiguous abbreviations are normalized;
- punctuation is finalized for pacing.

Outputs:

```text
generated/narration.wav
 generated/alignment.json
 generated/narration-manifest.json
```

`alignment.json` must contain word-level or finer start/end timing from provider alignment or a deterministic forced-alignment pass against the exact generated narration.

Narration manifest pins:
- `script_hash`
- provider
- provider model
- voice ID
- normalized spoken text hash
- audio SHA-256
- alignment SHA-256

The narration WAV is the single audio authority for all downstream stages.

## 7. Speech-driven host generation

Runway remains the host/performance-video provider, not the narration authority.

Canonical path:

```text
canonical narration WAV
-> stable hidden performance driver / supported speech-performance route
-> Act Two transfer to approved visible Satoshi plate
-> host.mp4
```

Rules:
- The exact canonical narration drives the host performance.
- No second TTS generation inside Runway may replace the master narration.
- Host generation is keyed by `script_hash + narration_audio_hash + plate_hash + host_provider_config`.
- A script change invalidates host performance.
- A graphics-only change does not invalidate host performance.

## 8. Timing-driven graphics and visual plan

Graphics and evidence receipts are keyed to the canonical alignment file, never estimated from total duration.

Examples:
- the `7.0` graphic appears on the aligned phrase `seven point zero`;
- an FDA card appears on the aligned FDA sentence;
- an LH/FSH mechanism graphic begins at the first aligned mechanism phrase.

Every graphic event records:

```json
{
  "event_id": "...",
  "anchor_words": "seven point zero",
  "start_seconds": 12.34,
  "end_seconds": 14.10,
  "claim_ids": ["claim-3"],
  "asset_id": "graphic-traverse"
}
```

Exact data, labels and evidence receipts use deterministic graphics. Generative video is reserved for clearly labeled illustration, metaphor or comedy where exactness is not required.

## 9. Remotion assembly

Remotion receives only pinned artifacts:
- canonical narration WAV
- alignment JSON
- generated host video
- deterministic graphics/event plan
- approved visual assets
- script/evidence manifest

The host/plate source is muted whenever canonical narration exists. The canonical narration WAV is the only final spoken track.

The rendered MP4 must be:
- H.264 video
- AAC-LC audio
- 48 kHz stereo
- fast-start enabled
- vertical 1080x1920 target unless an explicitly versioned preview format is requested

## 10. Quality gates

A render cannot become `review_ready` unless all automatic gates pass:

### Script/evidence
- `script_hash` matches the approved script.
- every factual segment has valid claim IDs and URLs.
- no stale draft from a prior writing-contract hash is reused.

### Audio
- exactly one canonical narration track;
- not silent;
- duration matches rendered video within configured tolerance;
- normalized listening level;
- final audio hash is recorded.

### Sync
- host generation was produced from the same narration hash;
- graphics use the current alignment hash;
- expected anchor events fall within timing tolerance;
- no host clip generated from a different script/narration revision can be reused.

### Visuals
- factual graphics match evidence records;
- generative reconstructions/illustrations are labeled where required;
- rights/provenance are recorded for external media.

Failure at any gate blocks publication and preserves diagnostic artifacts.

## 11. Persistence and URLs

R2 is the canonical media store.

For each successful render, write both:

```text
reels/<episode-slug>/<version-id>.mp4
reels/<episode-slug>/final.mp4
```

The versioned object is immutable. `final.mp4` points to or is replaced by the currently approved render only after review.

The run manifest records:
- object key
- public URL base used for review
- SHA-256
- script/evidence/rhetoric/narration/host/render hashes
- publication state

Instagram is the human-facing distribution/library, not the master archive.

## 12. Review and publication

State machine:

```text
conversation_received
-> brief_normalized
-> evidence_enriched
-> rhetoric_retrieved
-> script_drafted
-> script_locked
-> narration_generated
-> host_generated
-> visuals_ready
-> rendered
-> qc_passed
-> review_ready
-> approved
-> published
```

A failed stage remains resumable from the last durable successful artifact.

No render publishes automatically merely because it rendered successfully. The first production policy remains explicit human approval before Instagram publication unless the owner deliberately changes that release policy.

## 13. Idempotency and cache invalidation

Each stage has its own content-derived identity:

```text
brief_id      = hash(structured conversation brief)
evidence_id   = hash(brief_id + evidence configuration + source results)
rhetoric_id   = hash(brief_id + corpus/index version + selected mechanics)
script_id     = hash(brief_id + evidence_id + rhetoric_id + persona/writing-contract hash)
narration_id  = hash(script_id + normalized speech text + voice/model config)
host_id       = hash(narration_id + plate hash + host config)
visual_id     = hash(script_id + evidence_id + alignment hash + visual config)
render_id     = hash(narration_id + host_id + visual_id + Remotion version/config)
```

A retry with the same identity reuses the durable artifact. A changed upstream identity invalidates only dependent downstream stages.

Paid provider calls must persist reservation/task IDs before waiting. Ambiguous failures never trigger blind resubmission.

## 14. GitHub Actions orchestration

One top-level production workflow should own the episode state rather than separate user-facing workflows for research, speech, host and render.

Suggested entry point:

```text
.github/workflows/produce-satoshi-short.yml
```

It should:
1. validate the normalized chat request;
2. compute writing-contract and corpus/index identities;
3. enrich evidence and retrieve rhetoric;
4. generate/validate the script;
5. stop for script review when required;
6. generate canonical narration and timing;
7. generate/reuse host performance;
8. build deterministic visual events;
9. render;
10. run QC;
11. persist R2 versioned output;
12. expose one review URL and manifest.

Internal scripts may remain modular, but the operator should experience one pipeline and one episode state.

## 15. Migration from current repository

Current components should be reused, not rewritten wholesale:

| Current component | New role |
| --- | --- |
| `chat_request.py` | structured conversation normalizer |
| `topic_case.py` | hypothesis/research-case builder |
| `corpus_embeddings.py` | semantic rhetoric retriever |
| `reference_corpus.py` | deterministic fallback rhetoric retriever |
| `SATOSHI_PERSONA.md` | persona contract |
| `writing_contract.py` | writing/cache invalidation contract |
| `produce.py` / `satoshi_short.py` | evidence-backed synthesis writer |
| `satoshi_supervisor.py` | state coordinator, expanded to all stages |
| Runway adapter / `plate_host.py` | speech-driven host generation |
| `visual_director.py` / graphics code | timing-anchored visuals |
| Remotion | deterministic final composition |
| `render_audio_guard.py` | final audio/media integrity guard |
| `media_store.py` / `persist_media.py` | R2 durable persistence |

The dedicated TRT pilot becomes a test case of this same pipeline rather than a permanently separate production architecture. Its approved content can seed the conversation brief, but the final script, narration, host, graphics and render must use the same contracts as every future short.

## 16. Implementation order

1. Expand `chat_request.py` to preserve structured conversation fields.
2. Wire `corpus_embeddings.py` semantic retrieval into the writer with deterministic fallback.
3. Add segment-level provenance to script outputs.
4. Introduce a `speech_provider` adapter and ElevenLabs narration/alignment implementation.
5. Remove Runway TTS as narration authority; feed canonical narration into host generation.
6. Bind visual events to alignment timestamps.
7. Expand supervisor/state IDs through narration, host, visuals, render and R2 persistence.
8. Consolidate user-facing Actions into one top-level production workflow.
9. Migrate TRT into the unified path and use it as the end-to-end acceptance test.

## 17. End-to-end acceptance test

Given one conversation-derived TRT brief containing user jokes, editorial suspicions and factual candidate claims, one production run must produce:

- a structured brief preserving those human inputs;
- claim-specific web evidence with URLs;
- 3-5 retrieved Huberman-derived rhetoric mechanics or deterministic fallback;
- a Satoshi script with segment provenance;
- one locked narration WAV and alignment JSON;
- a host performance generated from that exact narration;
- timing-anchored evidence/comedy graphics;
- one QC-passing MP4;
- one immutable versioned R2 URL plus one stable episode `final.mp4` URL;
- a review manifest showing every upstream hash and source URL.

If any of those are missing, the singular pipeline is not complete.
