# GitHub Actions rhetorical corpus builder

Workflow: `.github/workflows/build-rhetorical-corpus.yml`

The workflow turns an authorized private transcript corpus into one stripped
semantic/rhetorical runtime index for the Satoshi writing system.

## Required setup

Keep bulk transcript files in a **private companion GitHub repository**, not in
this public media repository. Organize `.txt` or `.md` transcripts by source
family under `transcripts/`, for example:

```text
transcripts/
  huberman/
    episode-001.txt
  lwt/
    segment-001.txt
  revisionist/
    episode-001.txt
```

All three use the same embedding model and vector space. The source-family folder
adds retrieval metadata, not a separate embedding model.

Default routing is:

- `huberman` -> `explanatory`
- `lwt` -> `argumentative`
- `revisionist` -> `discovery`

Retrieval filters by `source_family` and/or `mode` **before** vector similarity
ranking. This avoids accidental style blending while retaining one compact
index.

Add these repository secrets to `media_platform_biotica`:

- `OPENAI_API_KEY` — used for rhetorical labeling and embeddings.
- `CORPUS_REPO_TOKEN` — read-only token able to checkout the private corpus repo.

Do not place either secret in source control.

## Running

From GitHub Actions choose **Build Rhetorical Corpus Index** and supply:

- private corpus repository (`owner/repo`);
- corpus ref, normally `main`;
- transcript path, normally `transcripts`;
- a stable cache namespace such as `rhetorical-v1`;
- `dry_run` first, then `live`;
- target maximum chunks, initially `5000`;
- embedding dimensions, initially `768`;
- a smoke-test narrative mode and optional source-family filter.

A dry run computes the corpus/chunk plan without calling OpenAI and reports how
many chunks fall into each source-family/mode namespace. A live run:

1. restores the most recent stripped runtime index from the Actions cache;
2. deterministically chunks current transcript files;
3. assigns source-family and narrative-mode metadata from folder structure;
4. compares chunk hashes with the existing runtime index;
5. sends only new/changed chunks for rhetorical labeling;
6. embeds those chunks with `text-embedding-3-small`;
7. stores vectors plus derived rhetorical metadata in SQLite;
8. runs a namespace-filtered semantic retrieval smoke test;
9. asserts that the persisted SQLite `text` column contains no transcript text;
10. uploads the stripped runtime index and validation reports as an Actions artifact.

Repeat runs therefore avoid OpenAI calls for unchanged chunk IDs.

## Privacy boundary

Source transcript text exists only in the checked-out private corpus workspace
and in-memory/API requests during the build. The uploaded runtime database does
**not** persist transcript passages. It stores relative source path/title,
source family, narrative mode, chunk hash, derived rhetorical labels/mechanics,
embedding configuration, and the vector.

## Initial enablement target

Start with roughly 2,000–5,000 chunks. The default `max_chunks=5000` deliberately
caps the first generation. Expand only after blinded evaluation shows semantic
retrieval improves the resulting scripts over the deterministic/tag baseline.
