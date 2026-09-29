# ChatGPT iOS → filmed plate → Satoshi short

## Product intent

You talk on **ChatGPT iOS**, attach or point at a **short filmed plate** of yourself,
say “run the Satoshi pipeline,” and get engaging men’s-health short-form video.
Optionally you may later add a **second avatar** for dialogue; today the short
path is still a **single-host monologue** (your plate on camera, or a Runway
avatar), with AI narration and graphics.

ChatGPT is the **operator**. GitHub + Actions are the **worker**. Chat memory is
not the media archive (`SPEC.md`).

## Operator loop (today)

1. **Conversation on ChatGPT iOS** — topic, jokes, questions, must-keep lines.
2. **Normalize to** `requests/satoshi/current.json` (ChatGPT Work / you paste JSON).
   Include plate fields when filming yourself:

```json
{
  "topic": "…",
  "core_thesis": "…",
  "candidate_lines": ["…"],
  "host_mode": "uploaded_plate",
  "plate_r2_key": "satoshi/plates/your-plate.mp4",
  "dialogue_avatar_id": "",
  "dialogue_notes": "optional future counterpart; ignored for render today"
}
```

3. **Upload the plate** to R2 (presign workflow or `media_store`) — MOV is accepted
   and normalized to MP4 — or set `plate_local_path` in a private runner.
4. **Push / run** `Produce Satoshi Video Preview` on `main` (needs Runway credits).
5. **Review** the private MP4 artifact; publish only via the gated Instagram Action.

## Host modes

| `host_mode` | On camera | `RUNWAY_AVATAR_ID` role |
|-------------|-----------|-------------------------|
| `avatar` | Runway custom avatar | Visible host |
| `uploaded_plate` | Your filmed plate | Hidden speech/performance driver (Act Two) |

## Not automatic yet

- ChatGPT iOS cannot push git or upload R2 by itself — use ChatGPT Work / Actions /
  a thin bridge you control.
- Dual-avatar **dialogue Reels** are not implemented; podcast dialogue modules are
  separate. `dialogue_avatar_id` is reserved on the brief only.

## Local smoke (plate present)

```sh
python3 chat_request.py --input requests/satoshi/current.json --output /tmp/resolved.json
python3 singular_video_preview.py --draft … --voice-id Vincent \
  --avatar-id "$RUNWAY_AVATAR_ID" --host-mode uploaded_plate \
  --plate-local-path IMG_4418.MOV --live --render
```
