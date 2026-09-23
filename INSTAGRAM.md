# Instagram Reels production path

The repository is Python-based. Its implemented modules now have a concrete
handoff: `web_research.py` / `research.py` → reviewed case → `writer.py` →
reviewed script → `pipeline.py` storyboard and footage plan → Remotion assembly
with a separately supplied host plate → `instagram.py` publication and
insights → `experiment.py` same-age descriptive comparison. Runway's API job
adapter, private media hosting and final visual QC are still pending. Measured
beat timing and reviewable phrase captions now exist in the Remotion path;
word-level audio alignment is still pending.
This is an **Instagram-first output**, even when a YouTube or Commons URL is
used to *discover* a visual lead.

## Script and visual handoff

The writer's `draft.json` has five narrative beats and `production_note` per
beat. A separate review JSON must contain `status: approved`, `reviewer`, and
`script_sha256` equal to `studio.digest(draft['script'])`. Optional
`visual_queries` maps beats such as `evidence` to concise searches. Run:

```sh
python3 pipeline.py storyboard --draft /private/draft.json --review /private/script-review.json --output outputs/storyboard.json
python3 pipeline.py discover --storyboard outputs/storyboard.json --output outputs/catalog.json
python3 pipeline.py plan --storyboard outputs/storyboard.json --catalog outputs/catalog.json --approvals /private/clip-approvals.json --output outputs/footage-plan.json
python3 pipeline.py package-remotion --plan outputs/footage-plan.json --plate /private/pedaling.mp4 --voice /private/narration.wav --loop-plate
cd remotion && npm ci && npm run studio
```

Every selected clip must link to one of the approved beats and its claim IDs;
the six-shot plan covers all five beats. `footage.py` can search Commons and,
with `YOUTUBE_API_KEY`, YouTube discovery. The first Google search is 100 quota
units and multiple beat searches consume more quota. Neither source automatically
provides a cleared clip. Instagram candidates can be supplied as a catalog with
`cue_id` and `candidates`, then passed via `pipeline.py discover
--instagram-catalog /private/ig-evidence.json`.
The separate `footage.py render` command remains a simple FFmpeg preview path;
the Remotion composition is the modular final assembly path. For plate duration,
optional looping and rendering, see [HOST_FORMAT.md](HOST_FORMAT.md).

## Reel lead search → screen-record → splice

For topic-driven Instagram VIDEO discovery (not Commons), use
`reel_search.py`. It searches hashtag Reels through the Graph API as the
configured professional account (for example `@byoticallc` via `IG_USER_ID`),
ranks leads by available like/comment counts, and writes a **recording queue**.
You screen-record those permalinks locally; the script then keeps only sources
under 10 seconds for rights review and pipeline splice.

```sh
# Requires META_ACCESS_TOKEN and IG_USER_ID for @byoticallc
python3 reel_search.py search --topic 'penile fracture' --cue-id evidence \
  --output outputs/reel-queue.json
# Screen-record each record_queue[].permalink into recordings/
python3 reel_search.py accept-recordings --queue outputs/reel-queue.json \
  --recordings-dir /private/recordings --output outputs/short-leads.json
python3 reel_search.py catalog --accepted outputs/short-leads.json \
  --output outputs/ig-evidence.json
python3 pipeline.py discover --storyboard outputs/storyboard.json \
  --instagram-only --instagram-catalog outputs/ig-evidence.json --output outputs/catalog.json
```

Hashtag search does **not** return other creators' view counts or durations.
Likes/comments are the ranking proxy; the `<10s` gate runs on local recordings.
Browser scraping is intentionally out of scope.

## Instagram discovery and source rights

The official Graph API with **Facebook Login** supports hashtag search and
`top_media` on a connected professional Instagram account. With the needed
app permissions/access token, run:

```sh
python3 instagram.py discover --tag menshealth --cue-id evidence --output outputs/ig-evidence.json
```

This returns video/Reel *leads* and permalinks. Hashtag top media measures a
platform ranking of whole posts. It does not provide the best seconds, a
general semantic search across every Reel, other creators' retention curves,
or permission to download and recut their videos. Ask the creator for the
original export and edited commercial use grant, including any music rights;
enter that source and grant into the footage approval manifest. An Instagram
URL is never accepted as a render source. A creator can instead provide a
licensed five-second excerpt, avoiding a full-Reel acquisition.

## Publication and measurement

Meta's official flow creates a `REELS` media container using a publicly
reachable HTTPS `video_url`, waits until status `FINISHED`, then publishes it.
`instagram.py create` and `publish` implement those separate steps and keep a
local SQLite ledger. **They are live calls.** Before `create`, supply an
editor-reviewed `approved_for_publication` JSON manifest with the local MP4
SHA-256, `file`, `public_video_url`, caption, reviewer, script hash and footage
plan hash. The current code checks the local hash; private hosting and checking
that the public URL serves identical bytes remain to be implemented.

```sh
python3 instagram.py create --release /private/approved-release.json --ledger /private/instagram-posts.sqlite
python3 instagram.py publish --job JOB_FROM_CREATE --ledger /private/instagram-posts.sqlite
python3 instagram.py insights --job JOB_FROM_CREATE --ledger /private/instagram-posts.sqlite --output /private/snapshot-48h.json
```

Set `META_ACCESS_TOKEN` and `IG_USER_ID` privately for these commands, with
`META_GRAPH_VERSION` if your approved app requires another supported version.
The Facebook Login route also requires the correct professional-account,
Page-linked and app-review permissions. Live status has not been smoke-tested.
Provider failures during submission stay marked *unknown* and require account
reconciliation before retry. No automated background polling or publication
schedule is configured.

Own-Reel insights snapshots include actual provider metrics and retrieval
time. Put two variants and their `published_at` and `snapshot_path` into an
experiment JSON, then run `python3 experiment.py --experiment FILE --output
REPORT`. The report requires at least 100 views each and comparable capture
ages (48±6 hours by default), and computes shares/saves per 1,000 views where
available. These observational differences are **not causal A/B evidence**:
Instagram's distribution and audience may differ. Use repeats and predeclared
variants before changing the editorial format. Public top-Reel popularity is
not the same as how Biotica viewers respond to an inset.

References: [Meta Reels publishing](https://www.postman.com/meta/instagram/folder/y6xustx/reels-publishing),
[hashtag search](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/hashtag-search/),
[own media insights](https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights/),
[copyright guidance](https://www.facebook.com/help/354736791367645/).
