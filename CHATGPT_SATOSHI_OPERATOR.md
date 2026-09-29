# ChatGPT → Satoshi → Instagram (`@byoticallc`)

## Product loop

1. Have a real conversation on **ChatGPT iOS** (or a Project using the prompt in `references/satoshi/chatgpt-operator-prompt.md`).
2. Say **“Satoshi”** / **“make this a Satoshi video.”**
3. ChatGPT emits `requests/satoshi/current.json` from that conversation + asks plate choice once.
4. Commit that JSON to **`main`** (path watch triggers production) **or** run **Produce Satoshi Video Preview** via `workflow_dispatch`.
5. Pipeline: research + Satoshi persona write → speech → Runway host on plate → Remotion → R2 → **auto-publish Reel to `@byoticallc`**.
6. Screen quality later in Instagram (ledger still blocks duplicate jobs).

This is **production**, not a private toy. “Unreviewed” in older wording meant “not claim-reviewed science,” not “don’t post.”

## Persona & audience (in-repo)

| Doc | Role |
|-----|------|
| [`SATOSHI_PERSONA.md`](SATOSHI_PERSONA.md) | Fictional CV, voice, reasoning sequence, guardrails (hashed into writing contract) |
| [`references/satoshi/audience.md`](references/satoshi/audience.md) | Men's-health Instagram audience |
| [`references/satoshi/chatgpt-operator-prompt.md`](references/satoshi/chatgpt-operator-prompt.md) | Paste into ChatGPT Project / Custom GPT |
| `references/corpus/exemplars/00-satoshi-persona-*.json` | Mode-specific writing mechanics |

Satoshi = failed cynical funny entrepreneur (Theranos-adjacent, Juicero, WeWork, CRISPR ethics-era adjacency, other flops). Fiction. Diligence + dark comedy. Never gene-edited children; never patient-punching.

## Plate sources

| Source | When | Where |
|--------|------|--------|
| Peloton / pedaling boilerplate | Default if you don’t film | R2 `satoshi/plates/…` — see `references/satoshi-plate-catalog.json` |
| Fresh ~10s film | ChatGPT asks you to record | Upload to R2 → `plate_r2_key` |

`RUNWAY_AVATAR_ID` drives performance when using a filmed plate; the plate is the on-camera body.

### Catalog gap

Actions currently have a default key (`satoshi/plates/trt-2026-09-28.mp4`). Expand the Peloton library in R2 and list keys in the catalog so ChatGPT can pick `peloton-01`, etc.

## GitHub Actions contract

Workflow: **Produce Satoshi Video Preview** (`.github/workflows/produce-satoshi-video-preview.yml`)

**Triggers**

- `push` to `main` touching `requests/satoshi/current.json` (and writing-contract paths)
- `workflow_dispatch`

**Required secrets / vars** (operator already placed Meta publish secrets)

| Name | Purpose |
|------|---------|
| `OPENAI_API_KEY` | Script / research |
| `RUNWAYML_API_SECRET`, `RUNWAY_AVATAR_ID` | Host performance |
| `R2_*`, `MEDIA_PUBLIC_BASE_URL` | Public `video_url` for Graph |
| `META_ACCESS_TOKEN`, `IG_USER_ID` | Publish (`IGAA…` → Instagram Graph; Page token → Facebook Graph) |
| `SATOSHI_AUTO_PUBLISH_INSTAGRAM` | Default `true`; set `false` to stop at R2 |

## Minimal handoff example

```json
{
  "topic": "…from the conversation…",
  "opening_strategy": "observation_first",
  "core_thesis": "…",
  "editorial_notes": "…",
  "candidate_lines": ["…"],
  "must_keep_lines": [],
  "open_questions": ["…"],
  "suspicions": ["…"],
  "historical_analogies": ["Juicero"],
  "visual_ideas": ["…"],
  "claims_to_verify": ["…"],
  "supplied_urls": [],
  "timing_notes": "Hook hard; one receipt; provisional close.",
  "avoid": ["patient jokes", "unsupported fraud claims"],
  "host_mode": "uploaded_plate",
  "plate_r2_key": "satoshi/plates/trt-2026-09-28.mp4",
  "model": "gpt-5.6-sol",
  "max_openai_usd": 2.0,
  "run_note": "Conversation-triggered Satoshi generation"
}
```

Validate locally: `python3 chat_request.py --request requests/satoshi/current.json`

## Not built yet

- One-tap ChatGPT → git push without a human commit
- Multi-plate picker tool inside ChatGPT
- Dual-avatar dialogue Reels

Until those exist, the polished path is: **ChatGPT emits JSON → human/agent commits → Actions produces + publishes.**
