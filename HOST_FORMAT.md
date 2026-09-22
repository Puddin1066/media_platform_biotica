# Satoshi Shkreli: host and visual inset

Satoshi is an original on-camera host of short, researched men's-health
episodes. The target grammar is a direct-to-camera satirical explainer: a
question, a sharp visual receipt, a tested explanation and a clear limit.
The writing should feel quick and curious while remaining sourced and humane.
The format may take inspiration from desk-host research shows; performance,
wording, jokes and voice must be Satoshi's own.

## Thirty-second vertical episode

- Write the five existing script beats (`opening`, `explanations`, `evidence`,
  `limits`, `next_test`) for a speaking host. Use `production_note` to specify
  the desired visual and its relation to the spoken sentence.
- Produce the avatar plate independently. A reusable 10-second pedaling or
  walking shot can loop; a one-minute plate can supply a selected 30-second
  span. Keep the area behind the upper-right inset clear in the plate. Add an
  episode-specific narration track, or use a plate whose own audio is already
  the approved performance. A Runway adapter and lip synchronization are still
  to be built.
- Curate footage by the particular visual cue, then review the exact selected
  interval and its relevance. Popularity of a whole Reel can help discover a
  candidate, but gives no objective score for its best five seconds.
- Trim the six reviewed five-second shots as individual muted assets with
  `pipeline.py package-remotion`. Remotion sequences them as an upper-right
  inset over the supplied host plate, while preserving source credits.
  A visual cut may be accelerated only when legible and accurately framed;
  retain source attribution and avoid implying the clip documents a medical
  event that it does not actually depict.
- The final Reel needs readable captions, source credits, safe framing and
  editorial review. Current rendering does not implement all those steps.

For a penile-fracture episode, the writer first needs reviewed medical claims.
Possible visual cues include a relevant licensed clip for the opening question,
an anatomical graphic for the explanation, and a primary-source excerpt for
the evidence beat. A popular Reel of an unrelated accident is not evidence of
the diagnosis. Source selection follows the writing and its claim IDs.

The current pipeline handles reviewed script handoff, footage discovery leads,
editor selection and a local Remotion handoff. It does not identify high-retention spans
in third-party Reels, acquire third-party video rights, create Satoshi's avatar,
or create a captioned publishable master automatically.

## Remotion handoff

```sh
python3 pipeline.py package-remotion --plan outputs/footage-plan.json \
  --plate /private/pedaling.mp4 --voice /private/narration.wav \
  --loop-plate --output-dir remotion
cd remotion && npm ci && npm run studio
# After reviewing the preview: npm run render
```

For a one-minute plate, omit `--loop-plate` and use `--plate-start 12`, for
example. The packager checks plate length and trims each approved footage
interval. Its `episode.json` is a preview manifest with script and footage
hashes; publication still requires the separate release review in
[INSTAGRAM.md](INSTAGRAM.md). `episode.json` and local assets are private
production artifacts; do not commit generated media or personal footage.
