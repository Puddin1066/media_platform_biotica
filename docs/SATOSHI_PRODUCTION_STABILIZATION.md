# Satoshi Studio Production Stabilization

## Objective

Refactor Satoshi Studio so a production request reliably progresses from episode request through editorial artifacts, voice, visual assets, Runway host, Remotion final render, R2, and Instagram without repeatedly consuming paid media, committing mutable runtime state to `main`, mixing stale artifacts, or requiring manual inspection of providers.

Terminal success requires a verified `reel.mp4`, public R2 URL, optional Instagram permalink, and machine-readable production manifest. A run must not report complete until those conditions are satisfied.

## Architectural rule

Git is the source of code and episode requests, not the runtime database. Remove per-stage `git add/commit/fetch/rebase/push` persistence from production. Runtime state and generated media belong under an immutable `production_id` in R2, with GitHub Actions artifacts used for debugging.

## Canonical state machine

`REQUEST -> SCRIPT -> PROSODY -> VOICE -> AUDIO_REVIEW -> ALIGNMENT -> VISUAL_PLAN -> ASSETS -> HOST -> ASSEMBLY -> VERIFY -> UPLOAD -> PUBLISH -> COMPLETE`

Create `studio/production_runner.py` as the single production orchestrator. Reuse existing module implementations where practical. The runner determines whether each stage is valid and reusable, incomplete, retryable, or requires intervention.

## Production identity and storage

Every run receives a unique `production_id`, e.g. `northeastern-video-2026-10-01-r12-a81f93`.

Store artifacts under:

- `studio/{episode_id}/{production_id}/voice/`
- `studio/{episode_id}/{production_id}/assets/`
- `studio/{episode_id}/{production_id}/host/`
- `studio/{episode_id}/{production_id}/final/reel.mp4`

Never silently mix artifacts from different production IDs. Explicit reuse from a prior production is allowed only when the source production ID, URI, and checksum are recorded.

## Production manifest

Persist one authoritative manifest to R2 after every state transition. It must record episode ID, production ID, status, publish authorization, stage statuses, artifact URIs, SHA-256 hashes, provider/job IDs where applicable, reuse provenance, and final output URLs.

Use atomic/versioned writes where practical. The GitHub runner must be able to disappear and a later runner must resume from this manifest.

## Paid-media and Runway protection

Classify stages by cost. Runway is expensive and must be idempotent.

Before any Runway submission:

1. Check for an existing completed host artifact.
2. Verify its SHA-256.
3. Verify compatibility with the source/narration hashes.
4. Verify explicit media-spend authorization.

Record the Runway job ID, submission timestamp, source hash, narration hash, resulting checksum, and R2 URI. The same `(source_hash, narration_hash)` pair must not create another Runway request unless `force_regenerate_host=true` is explicitly supplied.

A downstream failure never automatically invalidates a valid Runway host.

## Asset integrity

Replace generic checksum errors with diagnostics containing `shot_id`, expected SHA-256, actual SHA-256, R2 key, production ID, generating stage, and whether isolated regeneration is safe.

If one still is corrupt, repair/regenerate that asset only. Never weaken checksum validation and never invalidate unrelated voice/host assets.

## Remotion contract

Create an immutable `assembly_input.json` containing script, narration, alignment, visual plan, versioned asset URIs/checksums, host URI/checksum, captions, and graphics configuration.

Remotion produces `reel.mp4`. Before upload/publish verify: file exists, non-zero size, valid MP4, video stream, audio stream, reasonable duration, and expected dimensions.

## Final R2 and Instagram contract

Upload the verified final render to `studio/{episode_id}/{production_id}/final/reel.mp4` and record the public HTTPS URL in the manifest and GitHub Actions summary.

When `publish_instagram=true`, publish the final Remotion render, never the raw Runway host. Record the Instagram media ID and permalink. If publishing fails after a valid render, status becomes `render_complete_publish_failed`; a retry performs publishing only.

## GitHub Actions

Consolidate production around `.github/workflows/satoshi-studio-production.yml` invoking `studio/production_runner.py` once.

Inputs:

- `episode`
- `production_id`
- `allow_media_spend` (default false)
- `publish_instagram` (default false)
- `force_regenerate_host` (default false)
- `resume` (default true)

Use concurrency scoped to the production ID, not a global mutable-state lock. Different episodes may run concurrently.

Keep a request-based push trigger such as `studio/video_request.json` so an ordinary repository write can start a new production from current `main`; manual `workflow_dispatch` must not be the only trigger.

## Maintenance agent

Expand the existing maintenance agent to diagnose production Python, Remotion, orchestration, manifests, asset integrity, and deterministic CI failures. It may not modify secrets, weaken validation/checksums, change publishing authorization, silently increase spend, or set `force_regenerate_host=true` merely to escape a failure.

Its objective is to restore the production to a resumable state and continue until a verified final artifact exists.

## Retry and crash recovery

Use bounded stage-specific retries. A provider timeout is not automatically a failed provider job; query the recorded provider job before resubmitting.

On startup:

1. Read manifest.
2. Validate completed artifacts.
3. Find first incomplete/invalid stage.
4. Resume there.

A production with valid script/voice/assets/host and failed assembly resumes at assembly.

## Required regression test

Create a fully mocked deterministic integration test:

1. Script succeeds.
2. Voice succeeds.
3. Assets succeed.
4. Runway succeeds once.
5. Remotion deliberately fails.
6. Production stops.
7. Production resumes.
8. Existing Runway host is reused.
9. Remotion succeeds.
10. Final MP4 uploads.
11. Instagram publishing succeeds.

Assertions:

- `runway_generation_count == 1`
- `remotion_attempt_count == 2`
- final MP4 exists
- public URL is non-null
- Instagram permalink is non-null
- production status is complete

No test may call a paid provider.

Also test single-asset corruption, stale artifact from another production ID, runner interruption, transient R2/Instagram failures, Runway timeout recovery, unauthorized host regeneration, duplicate triggers, checksum diagnostics, resume after assembly, and publish-only retry.

## Observability

Every run ends with a concise report showing each stage as reused/generated/repaired/complete/failed, Runway generations during this run, final public video URL, and Instagram permalink.

## Current Northeastern migration

Do not restart the Northeastern episode from scratch. Inspect the existing artifacts, checksum them, import valid voice/assets/host into a new production manifest with reuse provenance, and start at the earliest genuinely incomplete stage. Expected start is approximately assembly. Do not invoke Runway merely as part of migration.

## Definition of done

This PR is complete only when the migrated Northeastern production runs through the new architecture and produces:

- verified motion-edited Remotion MP4;
- accessible R2 preview URL;
- Instagram post when authorization remains enabled;
- Instagram permalink;
- final production manifest;
- zero unnecessary Runway regeneration during recovery.

The intended operator experience is: `Run the Satoshi Studio` -> `Complete — watch it here.`

## Non-goals

Do not redesign Satoshi editorial personality, visual style, evidence-window format, topic selection, or script logic except where required for production reliability.