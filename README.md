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
```

The CLI validates a case packet and generates six deterministic JSON production
briefs. Identical inputs reuse the same artifact; changing the case or canon
produces a new identity. All briefs are explicitly blocked from publication.
The sample contains questions, not researched findings. Nothing here should be
presented as an actual completed investigation or media episode.

## What does not run yet

Live research and multiagent reasoning, model-authored scripts, Runway video and
speech, editing/rendering, approvals, hosted storage, and remote job execution
are specified in SPEC.md but not implemented. Adding credentials alone will
not activate these unimplemented modules. No background service is running.

## Next implementation slice

Import source excerpts with locators; implement structured OpenAI writing and
claim checks; return one annotated short script with citations and a shot list.
Then integrate speech, rendering and review before producing full episodes.
Use secure provider setup, never paste secrets into chat or commit credentials.

## GitHub

Repository: https://github.com/Puddin1066/media_platform_biotica
This repository is public by owner approval. Never commit credentials, private
health information, raw interviews, licensed full texts, or generated media.

See SPEC.md for architecture, stages and release acceptance requirements.
