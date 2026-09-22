# Build status — 2026-09-22

## Research milestone

Added bounded Europe PMC discovery, abstract normalization, DOI/PMID deduplication,
immutable evidence snapshots, hypothesis review templates and iterative search
plans. Optional OpenAI triage is gated by processing rights, credentials and spend
reservations; provider calls are tested with mocks. No automated claim approval,
full-text ingestion, Runway generation or publication is implemented. See
RESEARCH.md. Earlier entries below describe historical milestones.

## Writing milestone

Added writer.py: evidence packet checks, OpenAI structured writing adapter,
five-beat/citation validation, single-attempt ledger and cumulative estimated
spend reservations. 24 offline tests pass. Provider success and failure are
mocked; no paid smoke test has been performed. No live content generated.
Provider routing: Runway video/audio, OpenAI writing and optional images.
See WRITING.md for the current boundary; older entries below record v0.

## Executed successfully

- `python3 -m unittest -v`: 10 tests passed.
- `python3 studio.py validate`: seed case reference validation passed.
- `python3 studio.py preview --format all`: six blocked planning briefs created.
- GitHub destination supplied: Puddin1066/media_platform_biotica (public, owner approved).

## Release state

Development preview only. No researched men's-health conclusions, model-written
scripts, audio, video, public website, paid calls, publishing, outreach, or
background automation were produced or started. Seed hypotheses are editorial
questions awaiting source collection, not scientific findings.

## Implementation boundaries

Current verification status is supplied by the case author, not independently
adjudicated by this program. The compiler cannot approve a release. Every output
remains blocked even when claims are marked verified. A future release service
must enforce evidence, rights and human approvals independently of writer output.

## Immediate next work

1. Review retrieved sources and prepare a rights-cleared evidence packet.
2. Configure private persistence and replacement provider credentials.
3. Smoke-test OpenAI triage and writing with a bounded approved spend.
4. Produce and review one source-annotated short script.
5. Add Runway speech/video task adapters, durable jobs, rendering and QA.

Credentials alone do not implement these remaining modules. Do not represent
the starter as an operational autonomous studio.
