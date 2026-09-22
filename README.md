# media_platform_biotica
For producing various forms of Biotica media

## Inquiry Studio — development preview

A hypothesis-driven men's-health media studio, built around traceable evidence,
versioned editorial identity, and coordinated content formats. Mystery is the
core audience experience: a personally consequential anomaly, competing
explanations, evidence tests, and earned revelations—not generic health advice.

## What runs today

Python 3.10+; no third-party dependencies or credentials needed for this stage.
From this directory:

```sh
python3 -m unittest -v
python3 studio.py validate
python3 studio.py preview --format all
python3 exporter.py --format all
python3 pipeline.py bootstrap
python3 pipeline.py short-prompts
python3 produce.py --format short
python3 web_research.py
python3 research.py collect --page-size 3
python3 ui_server.py --port 8765
```

**Pipeline:** theme → research → writing → Runway media → review. See PIPELINE.md.
**Shorts:** dedicated prompt/script pack in `prompts/short.py` — see SHORTS.md.
Operator UI at `http://127.0.0.1:8765/` after starting `ui_server.py`.

**Primary media-text path:** `produce.py` drafts shorts, podcast segments,
newsletters and treatments with OpenAI Responses `web_search` as the evidence
mechanism. Dry run is default; live runs stay `review_required` and
`publishable: false`. See WRITING.md.

The CLI also validates a case packet and generates six deterministic JSON
production briefs. Identical inputs reuse the same artifact; changing the case
or canon produces a new identity. All briefs are explicitly blocked from
publication. The sample contains questions, not researched findings. Nothing
here should be presented as an actual completed investigation or media episode.

## What does not run yet

Web-search-primary drafting (`produce.py`), the step-wise orchestrator
(`pipeline.py`), operator UI (`ui_server.py`), and Runway media planning
(`runway.py`) are implemented with offline tests. Europe PMC remains an
optional specialist connector. Optional OpenAI evidence triage and a
post-review claim-packet writer (`writer.py`) are implemented with mocked tests.
Live Runway submission, image generation, editing/rendering, approvals, and
private hosted storage remain gated or unimplemented. No paid OpenAI or Runway
smoke test has been run in this workspace. No background service is running.

## Next implementation slice

Configure private persistence and replacement credentials, then smoke-test
`produce.py` (and optional `web_research.py` / `writer.py`) with an approved
budget. Integrate Runway speech/video and rendering next. OpenAI may provide
images and narrative writing; Runway is the required video and audio provider.
Use secure provider setup, never paste secrets into chat or commit credentials.

## GitHub

Repository: https://github.com/Puddin1066/media_platform_biotica
This repository is public by owner approval. Never commit credentials, private
health information, raw interviews, licensed full texts, or generated media.

See SPEC.md for architecture, stages and release acceptance requirements.

See STORAGE.md for private archive versus publication destinations. The manual
`Export production previews` GitHub workflow produces downloadable, public-safe
planning files only; no provider calls or credentials are used.
