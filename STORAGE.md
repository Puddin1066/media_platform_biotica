# Storage, exports and publishing

## Separate three functions

1. Generation: OpenAI writes and reasons; Runway generates selected media.
2. Master archive: private, durable storage of research, versions and assets.
3. Publication: manually publish approved copies to audience-facing channels.

Provider API retention is not a studio archive. Download output files promptly;
do not assume API results automatically appear as projects in consumer apps.
See https://developers.openai.com/api/docs/guides/your-data and
https://docs.dev.runwayml.com/guides/using-the-api/ for provider behavior.

## Proposed master layout (not provisioned)

- projects/PROJECT/canon/ — claims, people, hypotheses, corrections
- projects/PROJECT/research/ — permitted sources and interview records
- projects/PROJECT/episodes/EPISODE/REVISION/text/ — Markdown and Fountain masters
- projects/PROJECT/episodes/EPISODE/REVISION/audio/ — masters, stems, transcript
- projects/PROJECT/episodes/EPISODE/REVISION/video/ — renders and source assets
- projects/PROJECT/episodes/EPISODE/REVISION/release/ — approved platform packages

Private object storage (such as a private Supabase bucket) is the intended
machine archive; an owner-controlled Drive folder can be the editorial library.
Neither integration is configured yet. Private storage, backup and recovery must
be tested before allowing sensitive research into hosted production.

## Publication destinations

| Material | Master | Audience-facing copy |
| --- | --- | --- |
| Short video | Private MP4 + caption/script package | TikTok, Reels, Shorts |
| Investigation | Private video/source package | YouTube |
| Podcast | Private audio + stems + notes | Podcast host/RSS |
| Dispatch or short narrative | Private Markdown master | Substack proposed |
| Screenplay | Private Fountain/Markdown; later PDF | Selective producer sharing |
| Book | Private manuscript/outline | Selected excerpts, not automatic full release |

Substack is proposed as the public written companion, not as the master archive
or default destination for complete unpublished screenplays. No account was
created, no publication integration implemented, and nothing has been posted.

## Implemented now

`python exporter.py --format all` creates six folders with an outline, production
plan, source notes, JSON packet and checksum manifest. These are BLOCKED PREVIEWS,
not finished narration or media. The sample has no verified scientific claims.

After the workflow is merged to main: Actions → Export production previews →
Run workflow → choose a format. Download the public-safe preview artifact within
seven days. Public-repository artifacts are not private storage. Only the checked-in
public-safe seed is accepted; no secrets are injected into this preview workflow.

Live writing/rendering still require provider adapters, rotated credentials,
budget approval, private persistence and editorial review. This workflow cannot
make paid calls, even if model keys exist in GitHub secrets.
