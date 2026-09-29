# ChatGPT iOS → Satoshi episode

## Product (what you described)

1. Have a normal interesting conversation on **ChatGPT iOS**.
2. Say something like: **“Make this a Satoshi video.”**
3. The system picks a host plate:
   - **Default:** a boilerplate **Satoshi-on-Peloton** clip from a plate library, **or**
   - **Ask you:** film a quick **~10 second** clip in ChatGPT iOS and use that as the plate.
4. Run the Satoshi pipeline (script + speech + visuals + Remotion).
5. **Post to `@byoticallc`** on Instagram. You screen quality later in the IG library.

This is **production**, not a private “preview-only” toy. The old “unreviewed preview” wording meant “not claim-reviewed science”; it still ships a real Reel when auto-publish is on.

## Plate sources

| Source | When | Where it lives |
|--------|------|----------------|
| Peloton boilerplate library | Default when you don’t want to film | R2 keys under `satoshi/plates/…` (private; not in git) |
| Fresh iOS film (~10s) | ChatGPT asks you to record | Upload to R2, then `plate_r2_key` / `plate_local_path` |

Docs historically call the boilerplate a **pedaling plate** (`HOST_FORMAT.md`: `/private/pedaling.mp4`). Those files were **never committed** (correct — private media).

### Where the Peloton videos went

In this checkout / public repo there is **no Peloton library** — only `IMG_4418.MOV` as a one-off.  
Actions plate plumbing points at a **single** R2 object:

`satoshi/plates/trt-2026-09-28.mp4`

Drive→R2 ingest for plates **failed** earlier (missing ffprobe in that workflow). So the “many Peloton plates” are either still on your phone/Drive, or need to be re-uploaded into an R2 plate catalog.

## Operator loop (today vs ideal)

**Ideal (ChatGPT iOS):** one message triggers brief + plate choice + Actions run + IG post.

**Today (bridge still manual/Work):**
1. ChatGPT (or you) write `requests/satoshi/current.json`
2. Set plate:
   ```json
   {
     "topic": "…from the conversation…",
     "host_mode": "uploaded_plate",
     "plate_r2_key": "satoshi/plates/peloton-01.mp4"
   }
   ```
   or after you film ~10s, upload and set that key.
3. Run **Produce Satoshi Video Preview** on `main`
4. On success it **auto-publishes to `@byoticallc`** (`publish_satoshi_instagram.py`) unless  
   `SATOSHI_AUTO_PUBLISH_INSTAGRAM=false`

`RUNWAY_AVATAR_ID` is only the **hidden** speech/performance driver when using a filmed/Peloton plate.

## Not built yet

- Native ChatGPT iOS button that films 10s and pushes R2 + git without a bridge
- Multi-plate **library picker** (“use peloton-03”) as a first-class chat tool
- Dual-avatar dialogue Reels (field reserved; podcast dialogue is separate)

## Next concrete recovery for Peloton stock

1. Collect Peloton/boilerplate clips into R2, e.g. `satoshi/plates/peloton-01.mp4`, `…-02.mp4`, …
2. Add a tiny catalog JSON listing those keys for ChatGPT to choose from
3. Default `plate_r2_key` when the user says “make Satoshi” without filming
