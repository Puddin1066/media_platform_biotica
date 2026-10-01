# Satoshi Studio Software Assembler

## Purpose

The Software Assembler is the repository-level engineering agent for Satoshi Studio. Its job is to work backward from an explicit endpoint objective, inspect the current repository architecture, infer the smallest maintainable set of pipeline changes, and produce a reviewable engineering plan before code changes are applied.

It exists to prevent the exact failure mode that occurs when several partially overlapping pipelines accumulate over time: new work should extend or consolidate the current canonical Studio architecture instead of creating another parallel production path.

## Operating model

The assembler follows this loop:

1. **Objective contract** — state the desired endpoint, inputs, observable output, and acceptance criteria.
2. **Architecture crawl** — inspect Studio modules, GitHub Actions, runtime code, renderer code, tests, fixtures, and documentation.
3. **Current-state inference** — identify canonical entrypoints, shared helpers, production gates, stale paths, and cross-module dependencies.
4. **Gap analysis** — compare the endpoint contract with what the repository can currently execute.
5. **Assembly plan** — generate an ordered set of minimal code/workflow changes with exact paths and tests.
6. **Verification contract** — define what must pass before the endpoint is considered complete.
7. **Maintenance plan** — identify checks that prevent the same class of failure from returning.
8. **PR review** — persist the inventory and plan to a branch/PR. Direct-to-main model-generated code is prohibited.

## Endpoint-first examples

Good objective:

> Given an approved Satoshi script and visual plan, produce a playable MP4 with synchronized narration, host footage, evidence panels, captions, and a public R2 URL. Do not publish to Instagram. Success requires the assembly manifest to contain a reachable MP4 URL and the render-audio guard to pass.

Poor objective:

> Improve the media pipeline.

The assembler should force broad requests into observable endpoint behavior.

## Canonical Satoshi Studio architecture

The current canonical module graph lives in `studio/modules.json` and should be preferred over old monolithic workflows. The assembler must inspect that graph on every run rather than relying on a hard-coded historical pipeline.

Current module chain:

`Source → Research → Story → Script → Prosody → Voice → Audio Review → Alignment`

and

`Script + Research → Visual Plan → Assets`

followed by

`Audio Review + Alignment → Host`

then

`Audio Review + Alignment + Visual Plan + Assets + Host → Assembly → Publish`

A new pipeline is justified only when the endpoint is structurally incompatible with the canonical graph. Otherwise, the assembler should repair or extend the existing modules/workflows.

## Safety and authority boundaries

The assembler may:

- read the repository and build an architecture inventory;
- infer dependencies and canonical entrypoints;
- generate a structured implementation plan;
- save plan artifacts to a dedicated assembler run directory;
- open a PR containing the plan and future reviewed implementation changes;
- recommend archiving stale entrypoints while preserving shared runtime helpers;
- define tests and maintenance checks.

The assembler must not:

- push arbitrary model-generated code directly to `main`;
- disable tests or validators to make a run pass;
- weaken scientific, media-integrity, spend, or publish approval gates without explicitly naming the tradeoff;
- invent credentials, provider features, successful tests, or endpoint success;
- publish media as a side effect of a planning run;
- delete legacy code that current Studio modules still import.

## Artifacts

Each run writes to `studio/assembler/runs/<run-id>/`:

- `architecture_inventory.json` — repository snapshot with file type, dependencies, signals, hashes, and selected excerpts;
- `objective.txt` — exact requested objective;
- `plan.json` — machine-readable endpoint contract, gaps, ordered implementation plan, verification, maintenance, and risk controls;
- `PLAN.md` — human-readable engineering plan for PR review.

## Model policy

Default planner: `gpt-5.6-sol` with high reasoning.

The model is used for architecture inference and planning. Deterministic code performs crawling, hashing, dependency extraction, output validation, and artifact persistence.

The important control is not temperature. The planner uses a strict JSON schema and high reasoning. Future code-generation stages should use bounded file scopes and patch validation rather than freeform repository rewrites.

## Development phases

### Phase 1 — architecture + plan (implemented in this PR)

- repository crawler;
- endpoint objective input;
- Sol architecture planner;
- structured plan artifacts;
- GitHub Actions entrypoint;
- plan PR creation.

### Phase 2 — bounded implementation

For each implementation-plan step, create a proposed patch restricted to the paths named by the planner. Every patch must:

- apply cleanly to a fresh branch;
- pass syntax/type checks;
- pass targeted tests before broader CI;
- remain within the objective contract;
- be committed to the assembler PR branch, never directly to `main`.

### Phase 3 — autonomous repair loop

When a test or endpoint verification fails, the assembler may iterate within a fixed budget:

`observe failure → localize cause → propose smallest repair → rerun targeted test → rerun endpoint verification`

Stop conditions:

- endpoint success;
- repeated identical failure;
- budget exhausted;
- required credential/provider unavailable;
- proposed fix would weaken a safety or approval gate.

### Phase 4 — maintenance mode

Maintenance runs should inspect:

- failing GitHub Actions;
- stale or duplicate production workflows;
- dependency drift;
- unused Studio entrypoints;
- test gaps around recent production failures;
- mismatches between workflow environment variables and runtime gates;
- broken module dependency/status propagation;
- missing artifact/public-URL verification.

Maintenance should open a reviewable PR or issue; it should not silently change production behavior.
