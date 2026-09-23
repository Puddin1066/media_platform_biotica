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
python3 studio.py preview --format podcast
python3 exporter.py --format all
python3 research.py collect --page-size 3
python3 web_research.py
```

The CLI validates a case packet and generates six deterministic JSON production
briefs. Identical inputs reuse the same artifact; changing the case or canon
produces a new identity. All briefs are explicitly blocked from publication.
The sample contains questions, not researched findings. Nothing here should be
presented as an actual completed investigation or media episode.

`footage.py` provides a rights-gated topic-to-inset workflow for Commons video
and optional YouTube *discovery*. An editor must approve source files and
timecodes (or supply owner retention data) before a 30-second montage can render.
See [FOOTAGE.md](FOOTAGE.md). No YouTube download API or public segment-level
engagement feed is assumed.

`pipeline.py` links an approved OpenAI short script to beat-specific footage
and a Remotion assembly package. `instagram.py` supports hashtag lead discovery,
reviewed Reel publication through Meta's professional-account API, and own-Reel
insight snapshots; `experiment.py` compares variants at matched publication ages.
All live Meta operations require separately configured account access. See
[INSTAGRAM.md](INSTAGRAM.md). Optional Runway task submission and collection
are implemented without a live provider test; unattended publishing is absent.
The on-camera Satoshi Shkreli format, writing voice and timed inset intent are
specified in [HOST_FORMAT.md](HOST_FORMAT.md); the generated host itself remains
an externally supplied video.
`speech_timing.py` concatenates separately recorded beats and times visual cues;
`runway_media.py` optionally submits Runway speech and Act Two tasks with a
durable ledger. Remotion renders phrase captions and shot changes on that
timeline. The manual GitHub Actions integration fixture returns a synthetic
MP4 artifact to prove the offline path without creator media or provider keys.
`episode.py` coordinates five parallel Runway speech requests, optional host
generation, collection and the existing private Remotion render path. See
[EPISODE_PIPELINE.md](EPISODE_PIPELINE.md) for the executable episode contract,
commands and remaining provider and footage inputs.
Runway can also create optional five-second visual illustrations while footage
is being selected; those remain unapproved until an editor labels and reviews
them in the source plan.
`produce.py` can draft cited copy with web search, while `web_handoff.py`
requires an editor to map every line to reviewed claim IDs before a storyboard
can drive those media jobs.

## What does not run yet

OpenAI web-search discovery and Europe PMC literature discovery are implemented;
see RESEARCH.md. Both produce evidence candidates that still require review.
Optional OpenAI evidence triage is implemented with mocked tests.
Multiagent reasoning, Runway video and speech task adapters, image generation,
full production editing/QA, durable hosted approvals and private storage remain unimplemented.
A source-backed OpenAI writing adapter is implemented and tested with mocked
responses; it has not been tested against a paid account. See WRITING.md.
No background service is running.

## Next implementation slice

Configure private persistence and replacement credentials, then smoke-test web
research and writing with an approved budget. Integrate Runway
speech/video and rendering next. OpenAI may provide images and narrative writing;
Runway is the required video and audio provider.
Use secure provider setup, never paste secrets into chat or commit credentials.

## GitHub

Repository: https://github.com/Puddin1066/media_platform_biotica
This repository is public by owner approval. Never commit credentials, private
health information, raw interviews, licensed full texts, or generated media.

See SPEC.md for architecture, stages and release acceptance requirements.

See STORAGE.md for private archive versus publication destinations. The manual
`Export production previews` GitHub workflow produces downloadable, public-safe
planning files only; no provider calls or credentials are used.
