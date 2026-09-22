# Evidence window: topic-to-clip workflow

`footage.py` adds **discovery, an editor-reviewed plan, and local rendering**.
The script's upstream `production_note` and spoken claim should define the
visual cue; the `script_cue` field ties each approved segment to that decision.
The output is an inset montage or a corner overlay on a supplied Satoshi host
video. Neither discovery nor rendering publishes anything.
For the script-to-Instagram workflow, use `pipeline.py` and `instagram.py` as
described in [INSTAGRAM.md](INSTAGRAM.md).

## Run

```sh
python3 footage.py discover --topic 'testosterone blood sampling device' --output outputs/footage/catalog.json
YOUTUBE_API_KEY=YOUR_PRIVATE_KEY python3 footage.py discover --topic 'testosterone blood sampling device' --youtube --output outputs/footage/catalog.json
python3 footage.py plan --catalog outputs/footage/catalog.json --approvals /private/approvals.json --output outputs/footage/plan.json
python3 footage.py render --plan outputs/footage/plan.json --host /private/satoshi.mp4 --output outputs/footage/episode.mp4
```

The first command searches Commons for videos with direct file links and license
metadata; its metadata still needs review. The optional YouTube search returns
whole-video views/likes/comments, URL and license designation **as leads only**.
It does not fetch video bytes, retention data, or a five-second download.
Search result popularity is not proof that any particular interval is engaging.
The YouTube API key is supplied through the environment, never in this repository.

`/private/approvals.json` has exactly six approved entries for a 30-second strip:

```json
{
  "approvals": [
    {
      "candidate_id": "youtube:EXAMPLE_ID",
      "rights_status": "approved",
      "license_basis": "Creator granted commercial edited cross-platform use on DATE",
      "credit": "Creator name — original video title",
      "media_source": "/private/creator-supplied-master.mp4",
      "script_cue": "Show the device drawing while host names the assay",
      "start_seconds": 12
    }
  ]
}
```

Repeat with six *distinct reviewed shots* in a real plan. A YouTube lead needs
its own separately supplied original/authorized media source. Commons files
need explicit license and attribution review as well; a license tag alone does
not establish that every person, soundtrack, or third-party element is cleared.

For a creator who shares retention analytics, replace `start_seconds` with
`retention_samples`, an array of `{ "second": 0, "watch_ratio": 0.72 }`
at one-second intervals. The planner selects the contiguous five-second span
with the highest mean audience watch ratio. This is an **objective measure of
attention to the source video**, not evidence that the inset will perform well
for Biotica. When samples are absent, a human selects the timestamp; the plan
labels that provenance rather than inventing a segment engagement score.

Input-side FFmpeg seeking requests only the selected interval from a direct
HTTP file when the server and container permit it. **It cannot guarantee only
five seconds of network transfer**: some MP4 indexes, keyframes, redirects or
servers require extra reads. For predictable cost and quality, request an
original five-second export from a creator. Remote URL transfer behavior should
be checked before a production run. The renderer makes an H.264 640×360 inset,
then overlays it at the upper right of a provided host video. Captions, fit,
source credit display, technical QC and publication review remain downstream.

YouTube policy prohibits an API client from downloading or storing its video
without YouTube's prior written approval. YouTube Analytics retention requires
authorization from the owner of the channel. Sources:

- https://developers.google.com/youtube/terms/developer-policies
- https://developers.google.com/youtube/analytics/channel_reports
- https://commons.wikimedia.org/wiki/Help:Search
- https://www.mediawiki.org/wiki/API:Imageinfo
- https://ffmpeg.org/ffmpeg.html
