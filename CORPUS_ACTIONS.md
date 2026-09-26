# GitHub Actions rhetorical corpus builder

Workflow: `.github/workflows/build-rhetorical-corpus.yml`

The workflow turns an authorized private transcript corpus into a stripped
semantic/rhetorical runtime index for the Satoshi writing system.

## Required setup

Keep bulk transcript files in a **private companion GitHub repository**, not in
this public media repository. Store `.txt` or `.md` transcripts under a stable
directory such as `transcripts/`.

Add these repository secrets to `media_platform_biotica`:

- `OPENAI_API_KEY` — used for rhetorical labeling and embeddings.
- `CORPUS_REPO_TOKEN` — read-only token able to checkout the private corpus repo.

Do not place either secret in source control.

## Running

From GitHub Actions choose **Build Rhetorical Corpus Index** and supply:

- private corpus repository (`owner/repo`);
- corpus ref, normally `main`;
- transcript path, normally `transcripts`;
- a stable cache namespace such as `huberman-rhetoric-v1`;
- `dry_run` first, then `live`;
- target maximum chunks, initially `5000`;
- embedding dimensions, initially `768`.

A dry run computes the corpus/chunk plan without calling OpenAI. A live run:

1. restores the most recent stripped runtime index from the Actions cache;
2. deterministically chunks current transcript files;
3. compares chunk hashes with the existing runtime index;
4. sends only new/changed chunks for rhetorical labeling;
5. embeds those chunks with `text-embedding-3-small`;
6. stores vectors plus derived rhetorical metadata in SQLite;
7. runs a semantic retrieval smoke test;
8. asserts that the persisted SQLite `text` column contains no transcript text;
9. uploads the stripped runtime index and validation reports as an Actions artifact.

Repeat runs therefore avoid OpenAI calls for unchanged chunk IDs.

## Privacy boundary

Source transcript text exists only in the checked-out private corpus workspace
and in-memory/API requests during the build. The uploaded runtime database does
**not** persist transcript passages. It stores:

- relative source path/title;
- chunk index and SHA-256 hash;
- derived rhetorical labels/mechanics;
- embedding model and dimensions;
- embedding vector.

This makes the Actions artifact suitable as a runtime retrieval index without
turning the public media repository into a redistribution point for bulk source
transcripts.

Changing chunking rules, labeling policy, or embedding dimensions should use a
new `cache_namespace` (for example `huberman-rhetoric-v2`) so incompatible index
generations are not mixed.

## Initial enablement target

Start with roughly 2,000–5,000 chunks. The default `max_chunks=5000` deliberately
caps the first generation. Expand only after blinded evaluation shows semantic
retrieval improves the resulting scripts over the deterministic/tag baseline.
