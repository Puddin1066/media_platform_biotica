# Short creation — prompt & script pack

Vertical mystery shorts (TikTok / Reels / YouTube Shorts) for Inquiry Studio.

## Pack location

`prompts/short.py` — version `short-pack-1`

Wired into:
- `produce.py` when `--format short` (web_search + five-beat script)
- `runway.py` for `narration_speech`, `short_video`, `host_ride_plate` when format is short
- `pipeline.py short-prompts` / UI `GET /api/short-prompts`

## Beat map (30–45s)

| Beat | Seconds | Goal |
| --- | --- | --- |
| opening | 0–6 | Personal stake + anomaly |
| explanations | 6–14 | Competing hypotheses |
| evidence | 14–26 | One sourced finding |
| limits | 26–34 | What it cannot prove |
| next_test | 34–45 | Open question / next test |

Target spoken length: **90–140 words**.

## Preview

```sh
python3 pipeline.py short-prompts
python3 produce.py --format short
```

## Pipeline path for a short

1. Theme / hypotheses  
2. Research (web_search)  
3. Writing via short prompt pack  
4. Media: narration + short_video bed + host Peloton plate  
5. Review (never auto-publish)

Place `media/plates/ride.mp4` before live host-plate jobs.
