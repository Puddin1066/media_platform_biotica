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

`source -> research -> story -> script -> prosody -> voice -> audio_review`

`script + research -> visual_plan`

The source/research/story/script/prosody/voice/audio-review/visual-plan/host modules are individually executable in the generic `Satoshi Studio Module` workflow.

`host` reuses a video already stored under `satoshi/plates/` and writes `host_manifest.json`. It does not generate a new host file.

Production-heavy modules (`assets`, `assembly`, `publish`) remain adapters to the existing production runtime. They are deliberately not described as fully decomposed yet.

## Execute

The hosted board is [Satoshi Studio](https://satoshi-studio-livid.vercel.app/). Select one or more modules and run them directly from the board. Studio resolves dependencies, dispatches one module at a time, waits for its state update, and stops at review gates.

The browser never receives a GitHub credential and there is no per-run password. The Vercel server-side `/api/dispatch` endpoint has a fixed repository, workflow and module allowlist, and requires only the server-side `GITHUB_TOKEN`. Protect the Studio deployment itself with Vercel Authentication rather than adding an application-level run key.

Workflow files live at `.github/workflows/studio-<module>.yml`. They call the shared runner in `satoshi-studio-module.yml` with the module id fixed.

The workflow commits updated episode state/artifact manifests back to `main` and uploads debug output as a short-lived Actions artifact.

## UI

`studio/index.html` is a zero-build control board. It reads the module registry and current episode manifest from `main`, refreshes every 15 seconds, surfaces failures/stale states, supports dependency-aware execution queues, and links to artifacts.

Publish remains explicit and asks for confirmation before dispatch.
