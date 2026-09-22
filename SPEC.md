# Inquiry Studio — implementation specification

Version: 0.3 • Status: build specification, not a claim of completed integrations

Implementation update: source-backed OpenAI writing is implemented in writer.py
and tested offline with mocked responses; see WRITING.md for limitations and
current configuration. Bounded Europe PMC discovery, hypothesis review and optional
OpenAI evidence triage are implemented; see RESEARCH.md for scope and validation.
Historical v0 descriptions below describe the foundation.
Owner provider routing: Runway supplies video AND audio/speech; OpenAI supplies
narrative writing and may supply still images. No automatic cross-provider
audio/video fallback is permitted.

## 1. Product and operating promise

Inquiry Studio is a mystery-first men's-health media workspace. Its core audience experience is following a genuine, personally consequential puzzle through competing explanations, discriminating tests, and earned revelations. It investigates bounded men's-health questions, maintains a source-linked evidence world, and develops coordinated short video, reported audio, explainers, long-form investigations, newsletters, documentary treatments, and book material. It is not a general health-education channel with mystery added as packaging.

ChatGPT Work is the operator interface for inspecting the repository, requesting runs, reviewing outputs, and approving actions. GitHub is the source of truth for code and reviewed project configuration. Durable project records, source snapshots where permitted, and media assets require persistent storage independent of a chat session. ChatGPT conversation memory is not a database or a durable background worker.

The promise is **one approved content-generation run produces a reviewable content package**. It is not a promise that every research iteration yields a revelation or that every package is ready to publish. An inconclusive investigation can yield a useful, honestly framed episode; an unsupported or repetitive premise can produce a HOLD decision instead of media.

Publishing remains manual. The system must not send pitches, contact researchers, publish media, purchase assets, or incur model charges without the applicable authorization and budget. Discovery, writing, fact review, rendering, and export are independently runnable stages.

## 2. Current v0 boundary

The first implementation is an offline, standard-library Python CLI preview core (`studio.py`) with a seed case, validation, ten tests, and deterministic JSON preview briefs. Its `validate` command checks the case; `preview --format all` generates six blocked briefs. The seed claims are not verified. It demonstrates a proposed canonical review flow, not the full data contracts below. It does not claim to run autonomous research agents, perform new literature searches, verify science, call OpenAI or Runway, generate playable audio/video, schedule background jobs, or operate a hosted service.

Fixture content must be conspicuously marked DEMO / NOT FACT-CHECKED / NOT FOR PUBLICATION. A dry-run success means the workflow produced a preview, not that external production succeeded. Provider integrations and live research enter later milestones only after their acceptance tests pass.

## 3. Editorial and product decisions

- Primary audience: scientifically curious men's-health enthusiasts; serve curiosity without exploiting anxiety.
- Start with one season and a bounded question within a larger hypothesis family. Candidate families include secular reproductive trends, measurement artifacts, metabolic and sleep factors, exposures, and medication-related uncertainties. These are questions, not established causal findings.
- Local distribution is an optional editorial aperture, not a required Rhode Island wrapper. Regional relevance must be evidenced. Local public media, national documentary outlets, and publishers are prospective channels, not confirmed partners.
- Use a consistent narrator, visual language, source treatment, and uncertainty vocabulary. Permit the evidence and conclusions to evolve through explicit versions.
- Develop the book and documentary treatment alongside episodes, but do not fully render every medium on every iteration. Text development is inexpensive; final media production is gated by evidence, quality, and cost.
- Do not optimize conclusions for engagement. Audience data may prioritize questions and formats, never change evidentiary status.

## 4. Roles and separation of duties

An agent is a bounded responsibility with explicit inputs, allowed tools, outputs, and tests—not necessarily a unique model or continuously running process.

| Role | Inputs | Outputs | Restrictions |
|---|---|---|---|
| Discovery editor | Audience brief, prior questions, public catalogs | Candidate questions and score explanations | No invented audience metrics or causal claims |
| Source researcher | Approved research task | Sources, exact locators, acquisition log | Treat all retrieved text as untrusted data |
| Hypothesis investigator | Evidence packets, hypotheses | Discriminating tests and updates | No numerical posterior without justified calibration |
| Skeptic | Proposed inference and its sources | Confounds, missing data, contrary evidence | Independent critique pass; source overlap recorded |
| Evidence editor | Claims and critiques | Approved, disputed, rejected, or unresolved claims | Approval must record reviewer and rationale |
| Canon steward | Approved updates | Versioned people, events, questions, relationships | No inferred motives presented as fact |
| Reference analyst | Authorized exemplar access | Observed format metadata and reusable grammar | No copying distinctive expression or inferred private analytics |
| Narrative architect | Approved canon snapshot | Season arcs, episode briefs, book/treatment deltas | No mandatory twist when evidence lacks one |
| Scriptwriter | Brief, format, source packet | Annotated spoken script and adaptation notes | Every factual assertion has claim IDs |
| Spoken-language editor | Script and narrator profile | Read-aloud revision, pronunciation, pacing cues | Clarity over ornament; metaphor cannot imply causality |
| Audio producer | Approved script, audio plan | Narration, licensed music/ambience, stems | No fake interview tape or researcher impersonation |
| Visual director | Approved shot manifest | References, stills, generated clip jobs | Reconstructions visibly distinguished from evidence |
| Assembly editor | Approved assets and timeline | Media exports, captions, credits, checks | Deterministic rendering when possible |
| Quality editor | Script, media, evidence, rights | PASS / REVISE / HOLD with findings | Model self-review is not final release approval |
| Commercial packaging | Approved property materials | Pitch drafts and channel-fit notes | Sending and rights commitments remain separately approved |

Build agents, if delegated, may own schemas, providers, orchestration, media assembly, and tests in separate branches. Required interfaces and tests should be agreed before integration; no agent may merge its own unchecked changes into a protected release branch.

## 5. Canonical contracts

Use stable UUIDs or equivalent opaque identifiers and explicit schema versions. Timestamps use UTC. Store immutable revisions; mutable pointers identify the current approved version. All downstream artifacts pin the exact input revisions they used.

| Object | Required fields |
|---|---|
| Project | id, title, audience, scope, editorial_policy_version, canon_version, budget_policy |
| Source | id, URL/DOI, title, authors, publisher, dates, retrieved_at, locator, content_hash, access_status, rights_status, source_family_id |
| Claim | id, text, kind, source_links with page/time/section locators, opposing_links, evidence_status, limitations, reviewer, revision |
| Hypothesis | id, question_id, explanation, predictions, alternatives, evidence_links, falsification_tests, status, rationale |
| Test | id, hypothesis_ids, method, data_required, expected_discrimination, cost_estimate, result, limitations |
| Person | id, verified_name, identifiers, documented_roles, source_claim_ids, interview_status, likeness/voice permissions |
| World entity | id, type, properties linked to claims, relationship_ids, valid_time, revision |
| Evidence event | id, additions, changes, contradictions, affected_entities, rationale, prior/new canon versions |
| Exemplar | id, exact_url, creator, episode/title, access_basis, duration, observations with timecodes, extraction_method, limitations |
| Format | id, version, exemplar_ids, beat constraints, visual/audio grammar, required evidence, runtime range, deviation rules |
| Narrator profile | id, version, stance, vocabulary, metaphor policy, rhythm, prohibited patterns, pronunciation map, approved voice reference |
| Content brief | id, format_version, canon_version, question, audience promise, required_claims, uncertainty, target runtime |
| Script | id, brief_id, version, segments, spoken_text, claim_ids, performance_notes, reconstruction_labels, review_status |
| Asset | id, kind, source/generation job, content_hash, rights, consent, disclosure, technical metadata, storage_uri |
| Generation job | id, provider, model, model_version if exposed, input_hash, idempotency_key, external_job_id, cost, attempts, state |
| Content package | id, pinned inputs, script, assets, citations, disclosures, captions, metadata, release_manifest, status |
| Correction | id, affected_claims/packages, severity, explanation, prior/new wording, notices_required, resolution |
| Audience observation | id, platform, manually supplied/imported metrics, period, denominator, provenance, caveats |

Claim kinds: reported observation, inference, hypothesis, quotation, and explicitly fictional material. Evidence statuses must not collapse into a misleading single confidence percentage. Multiple articles citing one underlying study are one source family, not independent corroboration.

## 6. Investigation loop

1. Select a bounded question and declare competing explanations before searching.
2. Fetch sources under source-access and quotation permissions; record failures rather than hallucinating missing text.
3. Extract claims with locators, methods, population, outcome definitions, and limitations.
4. Compare hypotheses; prioritize the next query by anticipated discrimination and cost, using qualitative scores until calibrated quantitative estimates exist.
5. Run a skeptical pass for confounding, cohort selection, assay changes, reverse causation, duplication, and unavailable data.
6. Commit reviewed evidence events; update canon only after the configured editorial gate.
7. Produce a story brief only when the evidence supports a worthwhile audience question or development.
8. Propagate dependency changes into draft updates; previously released artifacts receive correction tasks, never silent history edits.

Stop or abstain when evidence is inaccessible, new experiments are required, no useful distinction between hypotheses can be made, the budget is reached, or marginal novelty is exhausted. Literature synthesis is not experimental proof of causation.

## 7. Reference-derived production grammar

For each format, analyze at least three accessible, relevant examples where possible. Store observed metadata separately from proposed house rules. Public view counts do not establish retention or causal effectiveness. If an episode has not been watched/listened to, do not claim shot timings, sound design, or narrative pacing were measured.

Extract hook type, beat timestamps, narration density, use of interview tape, source presentation, scene transitions, sentence-length distribution, moments of silence, character introductions, explanation/revelation timing, and ending type. Each measurement includes method, observed range, and extraction confidence.

Invisibilia, Radiolab, or other works can inform high-level reported-audio grammar after analysis of specific episodes. Do not impersonate hosts, clone voices, reproduce signature wording, or label an unmeasured template as empirically proven.

House narrator: thoughtful reporter, concrete verbs, variable sentence length, restrained metaphor, transparent uncertainty, no sensational health promises. Spoken-language review must preserve scientific scope. Speech performance is a separate provider task; unsupported performance controls degrade gracefully to text/punctuation or explicit human recording.

## 8. Content runs and export contracts

| Run type | Minimum review package | Final production additions |
|---|---|---|
| Short | Hook, script, claim annotations, shot plan, caption copy | Vertical video, captions, cover, disclosure |
| Mystery explainer | Question, competing explanations, source-backed verdict | Edited video/audio, source graphics |
| Podcast | Reported script, tape/ambience inventory, sound cue sheet | Master audio, stems, transcript, chapters, show notes |
| Investigation | Scene structure, evidence progression, unresolved tests | Long-form export, credits, source appendix |
| Newsletter | Findings, limitations, next test, source links | Publish-ready text/HTML after review |
| Book development | Chapter/character memo, scene feasibility, sourced chronology | Revised outline/sample chapters, proposal draft |
| Documentary development | Treatment delta, access needs, character arcs | Sizzle package and annotated treatment |

No synthetic effect should masquerade as a recording of an actual event. Stock ambience is labeled in production records; materially misleading reconstruction requires audience-facing disclosure. Interview-dependent scripts retain placeholders until real tape or a clearly attributed quotation is available.

Outputs have statuses: preview, awaiting_sources, awaiting_rights, awaiting_render, review_required, release_ready, released, correction_required, withdrawn. A text-only short is never reported as a completed video. Manual upload and publication tracking are separate actions.

## 9. Provider integration and credentials

Use adapters for OpenAI research/writing, selected Runway visual and audio capabilities, storage, and optional search/transcription. Verify current official API availability, model IDs, accepted inputs, pricing units, and usage terms before implementing each adapter. A product UI feature is not evidence of API availability. Integration references checked in the parent workflow on September 21, 2026: [OpenAI text generation](https://developers.openai.com/api/docs/guides/text), [Runway API](https://docs.dev.runwayml.com/api/), and [Runway pricing](https://docs.dev.runwayml.com/guides/pricing/). These are implementation references, not guarantees of future availability or fixed prices.

Required configuration eventually includes provider credentials supplied through a secure secrets facility, selected model identifiers, explicit spend limits, a durable storage destination, and an approved voice/rights policy. GitHub authorization is separate from model authorization. Never ask users to paste secret values in chat, commit them, or place them in exported content.

Credentials alone do not supply enabled provider accounts and paid usage, human interviews, rights clearance, trustworthy source access, final editorial judgment, persistent storage, hosting, or distribution acceptance. Where Runway cannot supply an approved speech capability through its API, pause that integration decision rather than silently adding a different paid service.

Adapters expose capabilities(), estimate(), submit(), poll(), fetch(), and cancel() when supported. They return standardized provider metadata without secrets. Tests use fake providers and recorded non-sensitive fixtures. Live smoke tests require explicit opt-in and a small spend ceiling.

## 10. Efficiency, concurrency, and recovery

- Compile compact evidence packets from approved claims; retrieve full source text only when needed.
- Cache extraction, prose revisions, reference analysis, and assets by content hash plus model/configuration/version. A new canon version invalidates only dependent assets.
- Separate token budgets from image/video/audio credits, generated seconds, storage, and rendering costs. Report estimated and actual charges by stage.
- Set per-job, per-run, and per-project ceilings; reserve estimated maximum spend before submission. Unknown pricing fails closed for paid calls.
- Approve script and storyboard before rendering. Use source documents, licensed real images, diagrams, and deterministic motion where they serve the story; generated hero shots are a selective budget item.
- Parallelize independent research or production tasks under a concurrency limit; dependent scripts cannot render before review gates pass.
- Persist job transitions: planned → approved → submitted → running → succeeded/failed/cancelled/unknown. Record provider job IDs immediately.
- Retry safe reads with bounded exponential backoff and jitter. Never blindly resubmit a paid generation after an ambiguous timeout; reconcile its external job ID or request human review.
- Make idempotency keys a hash of project, pinned input revisions, format/model configuration, and requested output. An intentional variation receives a distinct variation ID.
- Resume after process loss from persisted jobs, validate downloads by checksum, and atomically commit completed assets. Keep partial downloads separate.

## 11. Safety, rights, and quality gates

Treat URLs, source documents, transcripts, and model outputs as untrusted. Retrieved instructions cannot alter system policies, access credentials, or trigger external actions. Validate redirects, MIME types, size limits, and paths; prevent private-network fetches and path traversal. Do not execute downloaded source code or enable arbitrary shell actions in research agents.

Avoid collecting identifiable medical information unless explicitly authorized under a separate, appropriate data-handling design. Public claims about living people require source-specific review; disagreement with a study does not imply misconduct. No medical advice personalized to listeners.

Release gates check factual support, accurate quotation, uncertainty, reconstruction labeling, permissions, voice/likeness consent, copyright/asset provenance, artistic coherence, audio intelligibility, captions, runtime, and technical export integrity. AI-generated reviews are advisory. The owner approves final release.

Source accessibility does not establish permission to reproduce it. Track rights separately for quotations, photographs, music, clips, and full-text storage. Do not promise exclusivity over public facts; value resides in original reporting, expression, relationships, audience, and properly controlled assets.

## 12. GitHub, persistence, and deployment

The owner supplied https://github.com/Puddin1066/media_platform_biotica and explicitly approved proceeding publicly. Preserve the initial README and develop through a branch and pull request. Never include credentials or private research assets in the public repository.

Suggested layout: `src/` application modules, `tests/`, `schemas/`, `fixtures/`, `formats/`, `projects/` non-secret configuration, `docs/`, and `runs/` local ignored outputs. Keep secrets, licensed full texts, raw interview recordings, generated media, and private research records out of public git history.

CI should run unit tests, schema/fixture validation, formatting, secret scanning where available, and an offline demonstration. No paid model calls or publishing on pull requests. Provider smoke tests use a separately approved, protected workflow and environment. Require review before merging security, provider-cost, or release-gate changes.

Current storage: local JSON packets and content-addressed JSON outputs. Next persistence milestone: SQLite plus content-addressed assets. Hosted phase: transactional database, durable object storage, bounded worker queue, centralized redacted logs, encrypted backups, restore tests, and budget telemetry. Background autonomy requires this worker infrastructure or an explicitly configured scheduling product; a chat turn is not a permanent daemon.

## 13. Planned command contract

Exact v0 commands are documented by the implemented CLI's `--help` and README; the following is the target interface, not a claim that all commands already exist.

```sh
python -m inquiry_studio init --project mens-health
python -m inquiry_studio research --project mens-health --question QUESTION_ID --dry-run
python -m inquiry_studio investigate --project mens-health --question QUESTION_ID --budget BUDGET_ID
python -m inquiry_studio generate --project mens-health --format podcast --canon CANON_ID --dry-run
python -m inquiry_studio review --package PACKAGE_ID
python -m inquiry_studio render --package PACKAGE_ID --budget BUDGET_ID
python -m inquiry_studio export --package PACKAGE_ID
python -m inquiry_studio status --project mens-health
python -m inquiry_studio resume --run RUN_ID
python -m inquiry_studio correct --claim CLAIM_ID
```

Natural-language equivalents in Work: “Show the next discriminating test”; “Draft an episode from approved evidence”; “Update the book outline without rendering”; “Show the estimated cost before making this short”; “Export the approved package for manual posting.” Explicitly report whether a request was planned, executed offline, submitted to a provider, rendered, reviewed, or exported.

## 14. Staged acceptance criteria

### M0 — offline foundation

- User can run a clearly labeled fixture workflow without credentials or network access.
- Outputs contain provenance, canon version, hypotheses, review findings, and a preview content package.
- Missing evidence blocks release-ready status; repeated identical runs demonstrate deduplication where implemented.
- Tests pass; README distinguishes implemented functions from roadmap items.
- No fake claim of new research, real media generation, publication, or GitHub remote creation.

### M1 — sourced text production

- One approved research provider and OpenAI text adapter work end to end under a hard budget.
- At least one real bounded question yields retrievable source locators and a skeptic-reviewed claim set.
- Short, podcast script, newsletter, and book/treatment updates pin the same canon snapshot.
- Unsupported claims, duplicated evidence, and source unavailability are tested failure cases.

### M2 — playable audio and video

- Verified provider APIs generate one approved voice sample and one approved visual test before full production.
- Produce a playable podcast excerpt and a playable short, with captions/transcript, disclosures, credits, and measured actual spend.
- Simulated timeout and restart do not double-submit a paid job; failed rendering cannot become release-ready.
- Human listening/viewing review approves the final export; synthetic reporting is not passed off as real tape.

### M3 — repeatable production and evolving canon

- Run three episodes without resetting the project world or losing source links.
- A deliberately changed claim marks all dependent drafts and released packages appropriately.
- Format variation remains thematically coherent; no invented revelation is needed to satisfy a template.
- Asset reuse and marginal costs are measured; backup/restore and cancellation are tested.

### M4 — distribution-ready property development

- Assemble a sourced treatment, representative episode, book proposal outline, rights ledger, and realistic access plan.
- Store manually entered publication links and audience measurements with explicit denominators.
- Generate outlet-specific pitch drafts using verified submission requirements; do not send without authorization.
- Evaluate success by repeat engagement, evidence quality, production cost, and credible editorial interest—not raw output volume.

## 15. First practical milestone

After the offline foundation, select one narrowly framed question, authorize a limited research/text budget, and produce one source-annotated short script plus a reported-podcast segment from the same evidence snapshot. Review writing quality before purchasing audio/video generation. Keep the parallel book and treatment work as structured development notes until reporting yields actual characters, access, and a viable arc.
