# Satoshi Studio MVP

Satoshi Studio is an artifact-driven control plane for Satoshi content production.

## Invariants

- One module per execution.
- Every module consumes explicit upstream artifacts and emits explicit outputs.
- Small JSON/text artifacts are committed to the episode workspace.
- Binary audio/video is persisted to R2 and represented in the workspace by manifests.
- Downstream artifacts are never silently deleted; upstream changes mark them stale.
- Script has a hard duration gate before voice/video spend.
- Publish remains a manual approval step by default.

## Current episode

`games-as-latent-therapeutics-2026-09-30`

## Implemented modules

`source -> research -> story -> script -> prosody -> voice -> audio_review -> alignment`

`script + research -> visual_plan -> assets`

`audio_review + alignment -> host`

`audio_review + alignment + visual_plan + assets + host -> assembly -> publish`

All registered modules now have executable runners. Assembly consumes the current
locked script and selected voice; it does not call a writer or regenerate speech.
Host modes explicitly distinguish a reused background plate from a speech-driven
Runway avatar / Act-Two plate. See [media production](MEDIA_PRODUCTION.md) for
contracts, existing provider requirements, retry behavior, and live verification
limits. The standalone Pipeline B Action remains a separate package-consuming
entrypoint; Studio reuses its production helpers for discrete module execution.

## Execute

The hosted board is [Satoshi Studio](https://satoshi-studio-livid.vercel.app/). Select one or more modules and run them directly from the board. Studio resolves dependencies, dispatches one module at a time, waits for its state update, and stops at review gates.

## Production library and backlog

The board lists episodes from `studio/library_index.json`. Choose an episode to
see saved script revisions, voice takes, stage readiness, and review gates.
Each successful module now copies its JSON/text outputs into
`studio/episodes/<episode>/library/objects/<hash>.<ext>` and records the
version, source file, input request hash, upstream versions, and media references
in that episode's `library.json`. Current script files remain easy to read;
earlier successful versions have their own stable links in the board.

Voice takes use content-hash R2 paths, so new takes do not replace older takes.
Generated visual/host/render assets already use hashed R2 keys where implemented.
The library backfill workflow catalogs existing current outputs without a
generation call. It labels backfilled files as current snapshots; it cannot
recreate historical R2 voice takes that were overwritten before this change.
Unpublished scripts remain in GitHub's repository rather than being uploaded to
the publicly served R2 media bucket.

Practical flow:

1. Choose an episode in Studio and review its research/story/script revisions.
2. Inspect the production plan and available voice/media. Run only incomplete
   modules; reviewed script and audio stages are explicit stop points.
3. Before Assets or Host, confirm the provider budget and available Runway
   credits separately. The board shows the configured cap but cannot query
   the account's actual balance. No backlog scan spends provider credits.
4. Review the assembled video, then explicitly choose Publish if desired.

`python studio_library.py plan` prints the same spend-free cross-episode
inventory for operators and agents. There is no unattended Runway batch
executor; a future batch run can use the index to submit only approved,
compatible episodes after a live credit check. Source rights and scientific
claims still need episode-level review before reuse.

The browser never receives a GitHub credential and there is no per-run password. The Vercel server-side `/api/dispatch` endpoint has a fixed repository, workflow and module allowlist, and requires only the server-side `GITHUB_TOKEN`. Protect the Studio deployment itself with Vercel Authentication rather than adding an application-level run key.

Workflow files live at `.github/workflows/studio-<module>.yml`. They call the shared runner in `satoshi-studio-module.yml` with the module id fixed.

The workflow commits updated episode state/artifact manifests back to `main` and uploads debug output as a short-lived Actions artifact.

## UI

`studio/index.html` is a zero-build control board. It reads the module registry and current episode manifest from `main`, refreshes every 15 seconds, surfaces failures/stale states, supports dependency-aware execution queues, and links to artifacts.

Publish remains explicit and asks for confirmation before dispatch.

## Opportunity Brief for hiring outreach

The board's **New Opportunity Brief** form accepts a company, role, decision
question, optional job URL and a topic brief pasted from a ChatGPT discussion or
Cursory submission. Creation commits an episode request and manifest together to
GitHub; it does not start a model or Runway job. Enter public business context
only. Studio does not have blanket access to past conversations.

Choose the new episode and run the existing modules in order. Source and research
verify public signals. Story and script use a 60–90 second professional format:
decision, sourced signals, inference, next step and a short role connection. At
least two distinct cited URLs are required. The Script stage archives
`source_brief.json`, alongside the locked script. Visual Plan accepts restrained
typography, sourced charts and supplied evidence. Assets blocks generated
illustrations; Host defaults to a locally rendered graphic canvas rather than
impersonating the applicant or spending Runway credits. Assembly renders a 16:9
video and archives an unsent `outreach_draft.json` pointing to its media URL.
Review the script, source brief, narration and video before sharing. Voice is
synthetic and must not be represented as a recording of the candidate.

The format reuses the same immutable media library and explicit review gates.
Instagram Publish is disabled for Opportunity Briefs. The outreach note is never
sent by this system. OpenAI writing, research, narration, alignment and R2
storage may incur their usual provider costs; the asset/host confirmation
continues to guard those stages even when this format uses local graphics.

<!-- production redeploy trigger after Vercel environment update -->
