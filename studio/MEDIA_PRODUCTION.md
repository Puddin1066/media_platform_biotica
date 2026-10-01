# Satoshi Studio media execution

This extends the current Studio module registry and dispatcher. It does not
introduce another monolithic workflow or rerun the editorial writer in production.
Studio uses the existing Editorial A helpers for immutable script/narration and
the Production B runtime helpers for Remotion, audio validation and distribution.
The standalone `satoshi-production.yml` entrypoint still consumes an Editorial A
package; it is distinct from Studio's individually dispatched media modules.

## Module contracts

| Stage | Consumes | Produces | Invalidated by |
|---|---|---|---|
| Alignment | Locked script, selected narration | Measured word and sentence timestamps, audio/script hashes | Script or narration |
| Visual plan | Script, research | Consecutive, nonoverlapping shot coverage, screen text and source labels | Script or research |
| Assets | Visual plan, script | R2 media refs, native typography/chart records | Script or visual plan |
| Host | Selected narration, alignment, chosen plate | Speech-driven video or explicitly unsynchronized background plate | Narration, alignment, host configuration |
| Assembly | All current media manifests | Reviewed-preview MP4, mixed-audio hash, input hashes | Any consumed artifact |
| Publish | Approved assembly | Distribution packet, Instagram permalink, durable publication ledger | Assembly |

Small manifests live in `studio/episodes/<episode>/artifacts`; binaries live in
R2. Illustrative image assets are generated with up to three concurrent workers.
Action runs commit module state and upload debug artifacts. Shared Studio
concurrency serializes state writers, and a rebase preserves unrelated main
changes. The UI continues to stop at `needs_review`; manually dispatching the next
stage approves the reviewed dependency, matching the preexisting Studio behavior.
A rerun of selected narration marks alignment, host, assembly and publish stale,
while preserving visual assets that still match the script.

## Speaking host

Set `host.mode` to `act_two` to preserve an uploaded cycling/walking plate.
Runway's `RUNWAY_AVATAR_ID` is a stable internal driver: batch avatar videos speak
segments cut from the exact selected WAV, then Act-Two transfers their facial
performance to the supplied character video. Segments use measured sentence
boundaries, include pauses, cover the full narration, and stay within 3–30 seconds.
A segment without a suitable boundary blocks production rather than cutting a
sentence on estimated word counts. `avatar` renders that driver directly.

The pinned Runway SDK 5.20.1 supports `avatar_videos.create` with
`speech={type: audio, audio: <uploaded URI>}`. No separate lip-sync provider is
required for this route. Account access, the configured avatar, input quality,
and mouth alignment still need a live production check. Generated drivers must
carry audio correlated with the selected master at zero offset; duration drift
is bounded. Those checks cannot certify the visible mouth. Review the assembled
video at the start, middle, segment joins and end before publishing.

`master_asset` / `background_plate` deliberately reuse an unchanged plate. Their
manifest says `lip_sync: not_applied`. They can produce a preview but publishing
requires `production.allow_background_host_publish: true` and assembly approval.
Select `act_two` in the episode request when a speaking host is required. Changing
that request changes its identity; regenerate standalone Editorial A packages before
Pipeline B reuse.

Provider task reservations and outputs are checkpointed to R2. A timed-out or
ambiguous reservation stays blocked across retries rather than resubmitting a
potentially paid task. `host_jobs.json` is scoped to the current audio/host input
identity. The default spend estimate is bounded by `PLATE_HOST_MAX_CREDITS` (650);
provider billing and avatar quality must be confirmed on a live run.

## Text and evidence panels

Whisper-1 word timestamps use the existing OpenAI account. A local timing tool
can instead provide its word records to `narration_alignment.align_words`.
Transcribed words must match the locked script after punctuation normalization.
Number spellings or other disagreements need correction using observed times;
there is no silent text rewrite or proportional timing fallback.

The canonical Remotion composition consumes `Caption` JSON, groups at most five
words per page and highlights the speaking word. Typography callouts are separate
from captions. Source labels come from actual research author/year metadata.
Screen text is rendered in Remotion, never baked into generated illustrations.

Supported shot records:

- `host`: keep the host unobscured.
- `typography`: native text card using `screen_text`.
- `chart`: native bars with explicit `chart.points` (label/value), `units`, and
  `source_url`. Missing data blocks execution rather than generating fake charts.
- `evidence`: explicit R2 `media.key`, `credit`, and optional `kind: video` and
  `playback_rate` (0.5–3). Image/video clips retain visible attribution. The tool
  does not scrape or screen-record third-party social videos.
- Other illustrative shot types: generated, labeled stills with frame-based
  motion. They currently do not create dynamic Runway B-roll. The plan prompt
  states this limit; a dedicated generated-video asset adapter can be added later.

The research role now explicitly invokes web search for primary sources and
counterevidence. Script claim IDs carry source URLs forward. Search output still
needs editorial scrutiny: citation presence is not independent verification.

## Sound and final mixing

Assembly synthesizes a short local reveal cue at up to four callout transitions;
`production.sound_design: false` disables it. Effects are quietly mixed and ducked
under narration using FFmpeg. This is sound design, not a music soundtrack, and
requires no new subscription. The original selected voice file remains immutable.
The final mixed WAV becomes Remotion's master soundtrack, so the existing audio
guard preserves the effects when normalizing/remuxing the final MP4.

## Run and review

From the board or the per-module Actions, execute the currently stale editorial
stages, then alignment and visual planning, then assets/host, then assembly.
Review the media URL in `assembly_manifest.json`. Only then dispatch publish.
The publish module verifies every current input hash, restores its durable
Instagram ledger, and resolves the published permalink into `distribution.json`.
The workflow also prints that permalink in the Actions summary.

Do not treat offline contract tests as a rendered quality or engagement result.
A live episode remains necessary to verify provider access, perceptual lip sync,
caption legibility, pacing, source accuracy, and final audio balance.
