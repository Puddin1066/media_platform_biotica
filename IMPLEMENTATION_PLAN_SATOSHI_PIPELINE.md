# Implementation plan: standalone Satoshi episode pipeline

This plan intentionally does not rewire or delete the existing Actions. It describes the implementation order for the new canonical pipeline defined in `CANONICAL_SATOSHI_CONVERSATION_PIPELINE.md`.

## Phase 1 — request and editorial contract

- Accept a conversation-derived request matching `schemas/satoshi_episode_request.schema.json`.
- Reject requests that collapse the source to a topic-only prompt.
- Preserve message IDs so strong lines, jokes, objections, and claims remain traceable to the conversation.
- Add a deterministic episode ID derived from the request digest.

## Phase 2 — conversation mining + research

Create a new orchestration module rather than importing legacy workflow orchestration.

The module should:
1. rank interesting, humorous, insightful, contradictory, memorable, and evidence-worthy moments;
2. identify a provisional thesis and strongest objection;
3. use OpenAI web-enabled research to verify consequential claims;
4. emit a claim graph with status: verified, disputed, unsupported, opinion, joke/analogy;
5. preserve strong operator phrasing when useful.

## Phase 3 — story graph and timed beats

Create the final narrative after verification.

Default roles:
- hook
- baseline belief
- belief origin/background
- receipt
- objection
- weird part / contradiction
- competing explanations
- men's-health bridge
- synthesis
- button/callback

Generate the hook after the body is known.

Every final beat must include source-conversation refs, claim status, citations where applicable, timing, visual intent, and spoken text.

## Phase 4 — host input

Host selection order:
1. new conversation-uploaded plate when explicitly supplied;
2. configured R2 plate;
3. configured default plate;
4. avatar fallback only when policy permits.

Validate media before any paid Runway operation. Store accepted new plates in Cloudflare R2 and include the R2 key/hash in the episode manifest.

## Phase 5 — cheap visual layer

Use OpenAI still generation as the default overlay provider.

Requirements:
- prompts are generated from the final beat meaning;
- no generic topic-keyword-only prompts;
- low-cost image model/quality defaults;
- no fabricated data, paper screenshots, logos, or identifiable real people;
- cache by normalized prompt/model/quality hash;
- output one or more stills per beat where editorially useful;
- Commons remains fallback-only;
- Runway-generated B-roll is opt-in/exception-only.

## Phase 6 — Runway host

Use Runway only for the moving Satoshi host by default.

The host generation step receives:
- final narration/script;
- validated plate/avatar reference;
- timing contract;
- provider budget cap.

Persist paid output immediately so a later render/publish failure does not regenerate it.

## Phase 7 — Remotion composition

Create a canonical composition driven by beat objects.

The evidence window must support:
- hold
- quick flip/montage
- push/slide
- crossfade
- slow zoom/crop
- intentional pause on a receipt or joke

The compositor also owns captions, citations/source labels, Biotica/Satoshi branding, and final deterministic timing.

## Phase 8 — QC and persistence

Fail before publish unless:
- `reel.mp4` exists;
- audio and video streams are present;
- narration duration and render duration are coherent;
- all required beat assets resolve;
- citations required by factual beats are present;
- final media is persisted to R2;
- final public URL is anonymously fetchable over HTTPS.

## Phase 9 — Meta/Instagram terminal stage

Publishing is downstream of render and storage.

Reuse the proven low-level Meta/Instagram integration where clean, but the new orchestrator owns the handoff contract.

Sequence:
1. final R2 public URL;
2. construct publish packet/caption/source metadata;
3. create Instagram Reel container;
4. poll processing status;
5. publish;
6. record post/container IDs and ledger metadata.

## Phase 10 — new GitHub Action

Only after phases 1–9 have executable modules and tests, add one visible production Action such as:

`Produce Satoshi Episode`

Inputs should be minimal:
- request path / request artifact
- live vs dry-run
- publish yes/no

The Action should orchestrate stages rather than contain business logic in YAML.

## Migration

Do not remove old Actions in the implementation PR.

After the new pipeline has successfully produced and published representative episodes, follow with a separate cleanup PR that marks existing workflows as retained utility, archived experiment, or superseded path.
