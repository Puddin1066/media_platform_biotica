# PR rationale

This change defines a new canonical Satoshi production contract without altering existing production workflows.

Why: the repository currently contains multiple overlapping Actions created during successive experiments. Rewiring them in place risks inheriting stale assumptions and making failures harder to isolate. The safer path is a fresh orchestration contract that selectively reuses proven low-level integrations.

Canonical production target:

conversation + optional host plate -> editorial mining -> research/verification -> story graph -> hook generated after body -> timed Satoshi beats -> OpenAI low-cost still overlays -> Runway moving host -> Remotion composition -> QC -> Cloudflare R2 -> Meta/Instagram publish.

This PR intentionally stops before adding another visible GitHub Action. The Action should be introduced only after the executable stage modules exist, so the repository does not gain another partially functional workflow.

Existing workflows remain unchanged.
