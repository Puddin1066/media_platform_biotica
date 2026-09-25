# Satoshi Shkreli: host and visual inset

Satoshi is an original on-camera host of short, researched men's-health
episodes. The target grammar is a direct-to-camera satirical explainer: a
question, a sharp visual receipt, a tested explanation and a clear limit.
The writing should feel quick and curious while remaining sourced and humane.
The format may take inspiration from desk-host research shows; performance,
wording, jokes and voice must be Satoshi's own.

## Deterministic monologue grammar

The five production beats are not enough by themselves. Every generated Satoshi short must also satisfy a fixed ten-move spoken grammar before it can enter production:

```text
opening      = cold_open -> comic_turn
explanations = stakes -> escalation
evidence     = receipt -> reveal
limits       = reversal -> qualification
next_test    = callback -> button
```

The writer returns these moves explicitly as `monologue_moves`. The beat's spoken `text` must equal the two move texts joined by one space; validation fails if the model adds hidden filler or changes the order. A 1–5 word `callback_anchor` chosen from the opening must recur verbatim in the callback move. This makes the rhetorical progression deterministic while keeping every actual line, analogy, joke, and performance original to Satoshi rather than copying another program's expression.

The move functions are structural: establish the premise, make an original comic turn, raise stakes, escalate, show a concrete evidence receipt, reveal what it changes, reverse the tempting overclaim, qualify uncertainty, callback to the opening, and finish on a sharp question/test/button. The grammar does not certify factual accuracy; the existing claim-review gates remain authoritative.

## Thirty-second vertical episode

- Write the five existing script beats (`opening`, `explanations`, `evidence`,
  `limits`, `next_test`) for a speaking host. Use `production_note` to specify
  the desired visual and its relation to the spoken sentence.
- Produce the avatar plate independently. A reusable 10-second pedaling or
  walking shot can loop; a one-minute plate can supply a selected 30-second
  span. Keep the upper-left evidence area clear in the plate. Add an
  episode-specific narration track, or use a plate whose own audio is already
  the approved performance. An optional Runway Act Two task can animate a
  character plate when a separate filmed performance is available. A silent
  pedaling plate plus audio alone does not supply that performance reference.
- Curate footage by the particular visual cue, then review the exact selected
  interval and its relevance. Popularity of a whole Reel can help discover a
  candidate, but gives no objective score for its best five seconds.
- Trim the six reviewed five-second shots as individual muted assets with
  `pipeline.py package-remotion`. Remotion sequences them as an upper-left
  inset over the supplied host plate, while preserving source credits.
  A reviewed shot may set `playback_rate` from 1 to 2; accelerate only when
  the visual stays legible and accurately framed;
  retain source attribution and avoid implying the clip documents a medical
  event that it does not actually depict.
- An optional `graphics.json` supplies an original episode headline in the
  lower third. Neither the headline nor the evidence panel depends on a
  particular show, episode, screenshot or downloaded reference footage.
- Remotion displays phrase captions using measured beat lengths and estimated
  timing *within* each beat. Review those timings, credits, face clearance and
  phone-screen legibility before approving any export.

For a penile-fracture episode, the writer first needs reviewed medical claims.
Possible visual cues include a relevant licensed clip for the opening question,
an anatomical graphic for the explanation, and a primary-source excerpt for
the evidence beat. A popular Reel of an unrelated accident is not evidence of
the diagnosis. Source selection follows the writing and its claim IDs.

The pipeline handles reviewed script handoff, footage discovery leads,
editor selection, measured per-beat narration, optional Runway speech or Act Two
jobs, and a local Remotion handoff. It cannot infer third-party Reel retention,
acquire reuse rights, or turn a silent pedaling plate into a talking face using
audio alone. Runway custom avatar videos can create a separate talking avatar
from approved audio, but that output is not automatically the pedaling plate.

## Remotion handoff

```sh
python3 pipeline.py package-remotion --plan outputs/footage-plan.json \
  --plate /private/pedaling.mp4 --voice /private/narration.wav \
  --timing /private/timing.json --loop-plate --output-dir remotion
cd remotion && npm ci && npm run studio
# After reviewing the preview: npm run render
```

For a one-minute plate, omit `--loop-plate` and use `--plate-start 12`, for
example. The packager checks plate length and trims each approved footage
interval. Its `episode.json` is a preview manifest with script and footage
hashes; publication still requires the separate release review in
[INSTAGRAM.md](INSTAGRAM.md). `episode.json` and local assets are private
production artifacts; do not commit generated media or personal footage.

## Speech and optional Runway jobs

Record five separate audio files in storyboard order, or generate them through
`runway_media.py submit-tts` and `collect` with a privately configured Runway
account. Each live submission has its own persistent ledger record and is never
retried automatically after an ambiguous response. The default is dry-run; a
live call requires `--live`, `RUNWAY_LIVE_ENABLED=true`, and a replacement
`RUNWAYML_API_SECRET`. Install `requirements-runway.txt` for live calls.

```sh
python3 speech_timing.py --storyboard outputs/storyboard.json \
  --opening /private/opening.wav --explanations /private/explanations.wav \
  --evidence /private/evidence.wav --limits /private/limits.wav \
  --next-test /private/next-test.wav \
  --output-audio /private/narration.wav --output-timing /private/timing.json
```

Speech longer than 30 seconds fails rather than silently speeding up. The
output records exact beat boundaries and keeps the existing script hash. Shot
changes follow the beat boundaries; five-word captions are timed approximately
within each beat and need a human sync pass. Runway's Act Two integration uses
`runway_media.py submit-act-two --character PLATE.mp4 --performance PERFORMANCE.mp4`.
The performance reference must be 3–30 seconds. Collect the returned task into
a local MP4, review it, then pass that MP4 as the plate for assembly.

The `Offline Reel integration fixture` GitHub workflow renders a clearly marked
synthetic test Reel with test patterns and tones. Download its artifact to
verify the complete remote path. It requires no secrets, paid calls or medical
claims. Real media is never checked into the public repository; a private asset
delivery mechanism and human approval remain required for a live episode.

For private inputs already on a trusted machine, `production_job.py --input-dir
/private/episode --render` builds the timing, clips and rendered MP4 in one
command after `npm ci` in `remotion/`. The directory contains `storyboard.json`,
`footage-plan.json`, `plate.mp4`, `audio/{opening,explanations,evidence,limits,next_test}.wav`
and local footage addressed by paths relative to that directory. Optional
`plate-options.json` controls `start_seconds` and `loop`. The job rejects
footage paths that escape the private directory.
