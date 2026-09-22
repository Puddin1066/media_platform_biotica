# Pipeline orchestrator & operator UI

## Flow

```
theme / hypotheses  →  research  →  writing  →  Runway media  →  review
```

1. **Theme** — load the men's-health case, select hypotheses + formats + media targets  
2. **Research** — OpenAI `web_search` memos (`web_research.py`)  
3. **Writing** — web-search-primary drafts (`produce.py`) for selected formats  
4. **Media** — plan/submit multiple Runway jobs (`runway.py`) for a holistic package  
5. **Review** — human gate; never auto-publish  

Each stage is dry-run by default. Operator may skip research or writing to proceed
when directed. Live calls still need `OPENAI_LIVE_ENABLED` / `RUNWAY_LIVE_ENABLED`
plus credentials and budget flags.

## CLI

```sh
python3 pipeline.py bootstrap
python3 pipeline.py start --format short --format podcast --media narration_speech --media short_video
python3 pipeline.py advance --run-id RUN_ID
python3 pipeline.py skip --run-id RUN_ID --stage research
python3 pipeline.py show --run-id RUN_ID
```

## Cost estimates

Each stage records:
- **estimate** — tokens (OpenAI) and/or job counts (Runway) converted to USD with
  editable operator rates
- **actual** — `0` on dry-run; from provider usage when live OpenAI returns token
  counts; Runway actual USD may be `n/a` (check Runway dashboard/credits)

The UI shows a full-pipeline planned total at start, a next-step preview, and
per-stage estimate vs actual cards.

## Runway capabilities (planned)

| ID | Endpoint | Role |
| --- | --- | --- |
| `narration_speech` | `POST /v1/text_to_speech` | Voiceover / podcast speech |
| `short_video` | `POST /v1/text_to_video` | Vertical short visual bed |
| `host_ride_plate` | `POST /v1/video_to_video` | **Your Peloton `ride.mp4` plate** as host visual |
| `avatar_presenter` | `POST /v1/avatar_videos` | Stock preset fallback only |
| `sound_bed` | `POST /v1/sound_effect` | Labeled ambience |
| `routed_audio` | `POST /v1/generate/audio` | Model-router speech |
| `routed_video` | `POST /v1/generate/video` | Model-router video |

Host plate path: `media/plates/ride.mp4` (gitignored). Or set `HOST_PLATE_PATH` /
`RUNWAY_HOST_PLATE_URI`. See `media/plates/README.md`.

Reference: https://docs.dev.runwayml.com/api/
