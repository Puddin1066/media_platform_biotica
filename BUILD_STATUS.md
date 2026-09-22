# Build status — 2026-09-22

## Instagram-native integration slice

`pipeline.py` connects exact-hash-reviewed OpenAI short scripts to visual cues,
catalogs, rights-gated 30-second plans and an FFmpeg host overlay. `instagram.py`
adds official professional-account hashtag discovery (leads only), a staged
container/publish adapter with local duplicate-submission protection, and
own-Reel insights snapshots. `experiment.py` makes descriptive same-age variant
comparisons from measured views and interactions. These provider calls are
mocked in tests; no Instagram account, Runway output, hosted media URL, live
publication or live insights were available in this workspace. See INSTAGRAM.md.

## Footage development slice

`footage.py` searches Wikimedia Commons for video metadata and, with a separately
configured API key, YouTube for whole-video leads. It plans six reviewed
five-second excerpts from licensed direct files; owner-supplied per-second
retention can select source-video windows. An FFmpeg renderer makes a montage
and optionally overlays it on a supplied avatar file. This has been verified
with an offline synthetic two-second render. No external footage, YouTube
download, avatar generation, captions or release approval is automated.
See FOOTAGE.md for inputs and limits. Historical status below predates this slice.

## Research milestone

Added an OpenAI Responses `web_search` adapter as the default broad-discovery
path. It records inline citations and consulted sources, caps tool calls, reserves
spend before each search, prevents duplicate submissions and marks every memo for
human review. Eight mocked/offline tests cover gates, citations, persistence and
ambiguous failures. No paid web-search call has been run because no replacement
credential is configured in this workspace.

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

- `python3 -m unittest discover -v`: 44 tests passed.
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
