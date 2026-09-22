# Source-backed narrative writing

## Provider roles (owner requirement)

| Capability | Provider |
| --- | --- |
| Narrative, scripts, spoken-language editing | OpenAI |
| Still-image generation | OpenAI permitted |
| Video generation and performance animation | Runway |
| Speech, audio and sound generation | Runway |

Do not silently route audio or video to OpenAI. If a required Runway capability
is unavailable via its API, report the specific blocker. Image generation
remains unimplemented. Optional Runway speech, custom-avatar and Act Two jobs
are in `runway_media.py`; no live provider call has been tested.

## What is implemented

`writer.py` builds a source-constrained Responses API request and validates its
structured script. It supports short, podcast-segment, newsletter and treatment
drafts. It does not yet implement autonomous research or multiple writer agents.
The short target is 60–85 words; `speech_timing.py` measures the actual
narration and fails when its five beats exceed 30 seconds.

Input uses the existing case JSON contract with these additional requirements:
- Reviewed claims: `text`, `reviewer`, `limitations`, known `source_ids`.
- Sources: `url`, `locator`, `excerpt`, `rights_status` of `permitted` or `public_domain`.
- Every source excerpt must be cleared for processing. Full-text availability
  alone is not rights clearance. Reviewer fields are owner assertions, not an
  automatic scientific verification.

Dry-run validation (no API call):

```sh
python3 writer.py --case /private/path/reviewed-case.json --format short
```

The existing men's-health seed intentionally fails this check: it contains no
reviewed evidence. Tests use conspicuously fictional evidence, not medical facts.

## Paid execution contract

Live writing requires all of: `--live`, `OPENAI_LIVE_ENABLED=true`, a securely
configured replacement `OPENAI_API_KEY`, model identifier, positive cumulative
`--budget-usd`, and verified `--input-usd-per-million` / `--output-usd-per-million`
prices. The CLI defaults to `OPENAI_MODEL` or `gpt-4o-mini`; account availability
must be tested separately. Do not reuse the keys exposed in conversation.

Budget accounting is a conservative byte-based input estimate with headroom,
plus the 2,000-token output limit, using operator-supplied pricing. It is not a
provider-enforced dollar cap. Prices must match the selected model. Reservations
accumulate in `outputs/writing/ledger.sqlite`; preserve this file across runs.
Deleting or changing the ledger location resets local spending history.

Each request is reserved transactionally before submission. Identical requests
are not automatically resubmitted after success, error, process interruption or
an ambiguous timeout. Inspect the ledger and reconcile provider charges before
any deliberate new attempt. Failed attempts retain their reservation.

Success writes `draft.json` (evidence snapshot, model, provider ID and usage) and
`script.md` to an ignored output directory. Status remains `review_required`.
Checks enforce five ordered mystery beats and valid claim references; they do
not prove that the words follow from those claims. Human review is mandatory.

## Remote status and limitations

The public GitHub preview workflow still makes zero paid calls. No paid writing
workflow is enabled: private persistent draft storage and a persistent ledger
must exist first. GitHub secrets do not automatically become local environment
variables here. No credentials have been read or tested in this milestone.

Reference: https://developers.openai.com/api/docs/guides/structured-outputs
