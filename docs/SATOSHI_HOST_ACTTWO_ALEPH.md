# Satoshi host: Act-Two + Aleph contract

## Goal

The speech-driven Satoshi host must use both Runway stages before Remotion:

1. **Act-Two**: synchronize the uploaded character/cycling plate to the approved narration/performance.
2. **Aleph**: transform the resulting synchronized footage according to the episode's Satoshi visual-treatment prompt while preserving the performance.
3. **Remotion**: composite the validated Aleph host with captions, evidence windows, citations, graphics, cuts, and final audio.

A requested speech-driven host MUST NOT silently fall back to the original background plate.

## Current defect

`studio_media.run_host()` currently supports `act_two`, creates narration-driven performance segments, applies Act-Two, concatenates the result, and hands that result directly to assembly. It has no Aleph stage. The workflow also has an insufficient-credit fallback that rewrites the request to `master_asset`, allowing an unsynchronized plate to be rendered as if production succeeded.

## Required implementation

### Host mode

Introduce a canonical host mode such as `act_two_aleph`.

For each <=30-second segment:

- produce/reuse the narration-driven performance reference;
- run Act-Two against the selected uploaded character plate;
- validate duration/audio identity;
- run Aleph on the Act-Two output using the episode's approved visual-treatment prompt;
- validate Aleph output duration and retain the segment's identity/provenance;
- persist each paid provider task and output so retries reuse successful work.

Concatenate the Aleph outputs into the final `host.mp4` and persist it to R2.

### Aleph constraints

Runway's current API documentation lists Aleph 2.0 (`aleph2`) as video-to-video, preserving input resolution, with 2–30 second input clips. The existing host segmentation is already <=30 seconds and is therefore the correct unit for Aleph processing.

The Aleph prompt must come from explicit episode/host configuration and be saved in the paid-job specification/hash. Changing the prompt invalidates only the Aleph output, not a valid Act-Two result.

### Cost guard

Preflight must calculate and report the costs of both stages separately. Current documented API pricing is 5 credits/second for Act-Two and 28 credits/second for Aleph 2.0. Do not submit if the API-project balance is insufficient for the requested live stages.

Report `api_credit_balance`, `estimated_act_two_credits`, `estimated_aleph_credits`, and `estimated_total_credits` in `host_readiness.json`.

Do not call this simply `Runway credits`; it is specifically the balance of the API project authenticated by `RUNWAYML_API_SECRET`.

### Failure behavior

For `act_two_aleph`:

- insufficient API credits -> fail HOST visibly;
- Act-Two provider failure -> fail HOST and preserve completed tasks;
- Aleph provider failure -> fail HOST and preserve Act-Two outputs;
- no automatic `master_asset` fallback;
- no Remotion assembly until the requested host pipeline completes.

Background/master-plate mode remains available only when explicitly requested.

### Manifest

Successful host manifest should record at minimum:

- `generated: true`
- `mode: act_two_aleph`
- final R2 media record
- narration SHA-256
- source plate SHA-256
- Act-Two segment task/output provenance
- Aleph segment task/output provenance
- Aleph prompt/hash
- `lip_sync: speech_driven_requires_visual_review`
- `visual_transform: aleph_requires_visual_review`

### Retry semantics

Paid jobs are idempotent by their specifications.

- Remotion failure reuses final Aleph host.
- Aleph failure reuses completed Act-Two segments.
- Act-Two failure reuses any completed earlier segments.
- A GitHub Action retry must query/recover known provider task IDs before creating replacement paid tasks.

## Acceptance test

Mock providers and prove:

`plate + narration -> Act-Two -> Aleph -> host.mp4 -> Remotion`

Then deliberately fail Remotion and resume. Assertions:

- Act-Two generation count does not increase;
- Aleph generation count does not increase;
- assembly retries and produces final MP4.

Also deliberately fail Aleph after Act-Two succeeds and prove retry reuses Act-Two.

## Production gate

Do not run the paid Northeastern episode until the GitHub Action's authenticated Runway API project reports the expected funded API balance. Once it does, run one production and return the final R2 MP4 for review.