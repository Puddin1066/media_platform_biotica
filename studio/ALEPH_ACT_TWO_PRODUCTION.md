# Satoshi: reusable Aleph setting + Act Two speech + rich overlay

## What this integrates

The current Studio graph remains Source → Research → Story → Script → Prosody → Voice → Audio Review → Alignment. Visual Plan/Assets and Host are independent branches; Assembly consumes both, and publishing keeps its review gate. This change adds `host.mode = "aleph_act_two"` to the existing Host stage and a shared adapter for the canonical plate-host path. It does not create another episode pipeline.

Studio's Satoshi production form saves these controls into the selected episode request and makes only visual_plan/assets/host/assembly/publish stale. It does not regenerate the approved script or voice and makes no paid calls itself. The browser's GitHub token currently requires **Contents write** for settings and **Actions write** for module dispatch. The connected GitHub worker has successfully run these model calls; that does not prove the browser token has those permissions.

```json
{
  "host": {
    "mode": "aleph_act_two",
    "r2_key": "satoshi/plates/my-upload.mp4",
    "aleph": {
      "prompt": "Replace the background with a comically malfunctioning scientific laboratory. Preserve the presenter's identity, face, clothing, bike and forward pedaling. Keep the face clearly visible and well lit. Steady camera, no baked captions.",
      "seconds": 10,
      "offset_seconds": 0
    },
    "performance_max_seconds": 4,
    "expression_intensity": 3
  },
  "production": {
    "max_overlay_images": 60,
    "max_runway_credits": 950
  }
}
```

Merge these fields into a complete existing episode request, rather than replacing its narrative/source fields. Longer host runs must fit both the request's estimate limit and the platform limit. Set the Actions variable `PLATE_HOST_MAX_CREDITS` deliberately (default 650). A 120-second speech track alone needs roughly 600 Act Two credits, plus driver and setting costs. These preflight estimates are **not a provider-enforced billing cap**; they conservatively include the setting even when cached.

## Tested API contract, October 3, 2026

| Job | Endpoint | Important inputs | Saved outputs |
| --- | --- | --- | --- |
| Setting plate | `POST /v1/video_to_video` | `model: aleph2`, `videoUri`, `promptText`, `outputFormat: mp4`, `targetAspectRatio: 9:16` | task ID; cost; immutable R2 MP4 |
| Speaking performance | `POST /v1/character_performance` | `model: act_two`; character **video** URI; reference **video** URI; `expressionIntensity`; `ratio: 720:1280` | task ID; cost; R2 MP4 |
| Poll | `GET /v1/tasks/{id}` | Bearer API key, `X-Runway-Version: 2024-11-06` | state, failure code/message, realized cost |
| Preflight | `GET /v1/organization` | same private API credentials | API project's credit balance |

Audio by itself is not an Act Two performance. The existing Runway avatar driver speaks the approved narration, its audio correlation is checked, then Act Two transfers its performance to the edited character plate. The master narration is mixed once during assembly. Visible mouth quality still needs human review; audio identity is not a lip-sync score.

Two four-second Aleph → Act Two tests completed successfully. Each cost 112 + 20 credits. The first resume test exposed re-encoding differences between runners and produced a second paid test; total qualification spend was 264 credits. After persisting original prepared inputs, a subsequent resume reused the original two task IDs without new model submissions. These are short qualification results, **not a completed two-minute production validation**.

## Recovery and reuse

- Fetch private source footage through authenticated R2, not its public browser URL. Public R2 requests from the worker returned 403 in the pilot.
- Prepared inputs are keyed by source checksum + offset/duration + normalization recipe. The first encoded bytes and reference are retained in R2. A fresh runner restores that exact media instead of encoding it again.
- Normalize to 24fps; explicitly forward-loop the character reference to the performance duration. Do not rely on automatic boomerang looping of a shorter plate.
- Stage request IDs include model/body/API version. Save request and reservation journals in episode artifacts and deterministic R2 objects **before** submission. Known task IDs can be polled; completed media is reused; ambiguous `reserved_unknown` submissions require reconciliation, never blind retry.
- Permission errors or transport failures from R2 do not count as a cache miss. Only a confirmed absent object permits generation.
- No automatic paid model retries are added. Preserve detailed provider failures/costs, and require an explicit new request after diagnosing a failed task.
- The Studio default uses short, measured word-boundary performance windows (4 seconds) because this is the driver framing actually tested. Increase it only after qualifying a longer face-forward driver. If there is no legal 3–maximum-second partition, stop with an actionable error rather than inventing timing.

## Overlay direction and timing

The writer plans a fresh image/reveal every 3–5 seconds, around 12–20 images/minute. Use claim-specific imagery, visual irony, absurd comparisons, self-deprecating gags, escalation and a closing callback. Prefer one strong focal idea that reads in a small square. Each shot retains its script excerpt, visual reason and humor device.

Long sentences can contain several image shots using `start_fraction`/`end_fraction` of their measured spoken interval. The validator rejects overlaps, gaps, unknown sentences and excess generated images before spending. Assembly turns those fractions into actual timeline frames. Approved narration is unchanged.

Image prompts include the actual sentence text, shot direction and comic device. Generated illustrations are labeled separately from evidence. Charts require sourced numeric values; source footage requires supplied R2 media and credit. Captions and citation cards remain deterministic Remotion text. Images are cached in R2 and can be restored when Assets reruns on a replacement runner. Portrait overlays sit below the presenter's face rather than covering mouth performance.

## Published workflow boundary

The supplied workflow `399c47b9-7199-42a4-b1bc-27c2f8905332`, observed version 17, contains Claude writing and three Seedance 2 shots (7/15/13 seconds); it is not the Aleph/Act Two path. Its named controls are registered separately in `runway_workflow_bindings.json`. The actual citation node is `d3585c43-57bb-4662-9405-a0f79f0ae49a`; overriding the citation label alone does not supply citation details. Model/graph changes require republishing that workflow. The production integration here continues to use Studio's OpenAI writer and locked audio.

Related open PRs #139–141 contain separate transaction, driver and layout changes. This PR is based on current main and is reviewable independently; overlapping host/layout changes should be reconciled when those branches merge.

## Verification

Offline tests cover cold-runner input restoration, complete-job reuse, ambiguous submission protection, R2 permission refusal, short performance partitioning, fractional overlay coverage, and the Studio narration/host handoff. Synthetic Remotion rendering checks the portrait panel and master audio. No new paid generations are required to review this PR.

Official references: [Runway API](https://docs.dev.runwayml.com/api/), [pricing](https://docs.dev.runwayml.com/guides/pricing/), [Act Two performance guidance](https://help.runwayml.com/hc/en-us/articles/42311337895827-Performance-Capture-with-Act-Two), [workflow publishing](https://help.runwayml.com/hc/en-us/articles/50682960972947-Publishing-a-Workflow-as-an-Endpoint).
