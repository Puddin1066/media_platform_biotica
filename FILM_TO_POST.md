# Film yourself → AI short → (optional) Instagram

This is the product path for Biotica Satoshi shorts.

```text
film plate (MOV/MP4)
  → upload to R2 / plate_host
  → topic or chat brief (requests/satoshi/current.json)
  → OpenAI script + Runway speech/visuals/host
  → Remotion private preview (publishable: false)
  → human review
  → release_instagram.py build + Publish Instagram Reel workflow
```

## 1. Produce a private preview (GitHub Actions)

Workflow: **Produce Satoshi Video Preview**  
https://github.com/Puddin1066/media_platform_biotica/actions/workflows/produce-satoshi-video-preview.yml

Needs GitHub secrets already used by that workflow: OpenAI, `RUNWAYML_API_SECRET`,
`RUNWAY_AVATAR_ID`, R2. Requires Runway credits.

This agent cannot `workflow_dispatch` that job (token 403). Start it from the
Actions UI on `main` after topping up credits.

## 2. Publish only after review (gated)

Workflow: **Publish Instagram Reel (gated)**  
`.github/workflows/publish-instagram-reel.yml`

Secrets: `META_ACCESS_TOKEN` (Facebook **Page** token), `IG_USER_ID`.

1. Build a release packet from the approved local/R2-backed MP4:

```sh
python3 release_instagram.py build \
  --file /path/to/reel.mp4 \
  --public-video-url 'https://…r2…/reel.mp4' \
  --caption '…' \
  --reviewer 'Your Name' \
  --script-sha256 '…' \
  --footage-plan-sha256 '…' \
  --output private/approved-release.json
```

2. Actions → **Publish Instagram Reel (gated)** → set `confirm_publish=true`
   only when you intend to post. Default is validation-only.

Preview pipelines never call Instagram. Publishing is always an explicit second step.
