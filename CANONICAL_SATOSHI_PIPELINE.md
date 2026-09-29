# Canonical Satoshi Reel pipeline

One workflow. One spend profile. Production Reels for `@byoticallc`.

## The product loop

```
ChatGPT / Cursor musings
  → requests/satoshi/current.json
  → Produce Satoshi Video Preview (Actions)
  → OpenAI websearch + Satoshi script
  → speech (ElevenLabs / configured provider)
  → lean insets (Commons stills → ffmpeg loops)
  → Runway host (avatar or filmed plate / Act Two)
  → Remotion assemble
  → R2
  → Instagram Graph publish
```

Operator doc: [`CHATGPT_SATOSHI_OPERATOR.md`](CHATGPT_SATOSHI_OPERATOR.md).  
Workflow: `.github/workflows/produce-satoshi-video-preview.yml`.

## Where tokens and credits go

| Layer | Spend | Role |
|-------|-------|------|
| OpenAI | Script + websearch enrichment | Research and Satoshi write. Keep `max_openai_usd` low on briefs. |
| OpenAI stills | ~$0.03–$0.30 / Reel | Six evidence-window insets by default (`SATOSHI_VISUAL_MODE=stills`) |
| Commons / web stills | Free metadata + download | Optional (`SATOSHI_VISUAL_MODE=lean`) when you want source photos |
| ffmpeg | Local | Still → 5s silent MP4 loop |
| Speech provider | ElevenLabs (preferred) or Runway TTS | Canonical narration |
| Runway | Host only in lean mode | Avatar or Act Two on filmed plate — **not** six Gen-4.5 insets |
| Remotion | Local | Final vertical Reel |
| R2 + Meta | Storage + Graph | Publish — `MEDIA_PUBLIC_BASE_URL` must be a **public** r2.dev/custom domain (not `*.r2.cloudflarestorage.com`) |

### Why lean is canonical

A 30s Reel with six Gen-4.5 insets burns ~360 Runway visual credits before the host runs. That is the wrong spend shape for Satoshi production: the host performance is the brand; insets should be real diagrams, gels, papers, and lab stills when possible.

Runway Gen-4.5 video insets stay available as `SATOSHI_VISUAL_MODE=ai` for moments that truly need invented motion — opt in, never the default.
## Visual modes

| Mode | Env / flag | Insets | Runway Gen-4.5 |
|------|------------|--------|----------------|
| **stills** (default) | `SATOSHI_VISUAL_MODE=stills` | OpenAI topic stills → loops (`openai_stills.py`) | **0** |
| **lean** | `SATOSHI_VISUAL_MODE=lean` | Wikimedia Commons stills → loops (`lean_visuals.py`) | **0** |
| **ai** | `SATOSHI_VISUAL_MODE=ai` | Six Gen-4.5 illustrations | 6 × 5s |

Override per run: `--visual-mode lean|ai` on `singular_video_preview.py` / `unreviewed_video_preview.py`.  
Repo var: `vars.SATOSHI_VISUAL_MODE` (workflow defaults to `stills`).
Image model/quality: `OPENAI_IMAGE_MODEL` (default `gpt-image-1-mini`), `OPENAI_IMAGE_QUALITY` (default `low`).

Commons candidates remain `rights_status: review_required` with license/artist credit on the shot. Lean does not invent a commercial clearance; it prefers attributable stills over paid generative filler.

## Host (always Runway when filming)

| `host_mode` | Body on camera | Notes |
|-------------|----------------|-------|
| `uploaded_plate` | Your Peloton / film plate from R2 | Preferred production look; Act Two drives performance |
| `avatar` | Runway custom avatar | Fallback when plate key 404s; supervisor soft-falls |

Plate catalog: `references/satoshi-plate-catalog.json`.

## What not to run

- Do not spin parallel “short” workflows for the same episode.
- Do not default to Gen-4.5 insets “for polish.”
- Do not treat ChatGPT conversation text as evidence — only `claims_to_verify` / `supplied_urls` + live websearch.

## Local smoke

```sh
# Dry-run lean path (no provider spend on insets)
SATOSHI_VISUAL_MODE=stills python unreviewed_video_preview.py \
  --draft /path/to/draft.json --voice-id Vincent --avatar-id "$RUNWAY_AVATAR_ID"

python -m unittest test_openai_stills test_lean_visuals test_unreviewed_video_preview test_footage -v
```

## Related modules

| Module | Job |
|--------|-----|
| `satoshi_supervisor.py` | Orchestrates research → media → publish |
| `singular_video_preview.py` | Speech seed + host mode + preview |
| `unreviewed_video_preview.py` | Visual mode, budget, plan, Remotion |
| `openai_stills.py` | OpenAI Images API → still loops (default insets) |
| `lean_visuals.py` | Commons discover → download → still loops |
| `footage.py` | `discover_commons_images` + rights-gated planning |
| `visual_director.py` | Six render slots from monologue grammar |
