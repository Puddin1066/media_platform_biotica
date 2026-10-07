# Satoshi v3

Satoshi v3 deliberately separates **editorial intelligence** from **production execution**.

## Where decisions happen

The ChatGPT/Claude conversation is the control plane. When the user says **"Satoshi this"**, the assistant uses the current conversation plus the Satoshi skills and web/social research tools to create a complete, approved episode manifest.

GitHub Actions does **not** research, choose a thesis, write a hook, repair model JSON, or decide what story to tell.

## Durable state

- `satoshi_v3/skills/` — Satoshi editorial rules.
- `episodes/satoshi/<episode>/episode.json` — approved production order.
- `outputs/satoshi-v3/` — run diagnostics/results.
- R2 / provider storage — generated media.
- Instagram — published output.

## Production contract

The v3 Action accepts only a completed `episode.json`. It validates that the manifest includes:
- episode metadata
- beats
- caption + hashtags
- verified source provenance with researcher/institution attribution

It then hands the approved manifest to the existing proven render/publish machinery.

This is transitional by design: v3 reuses stable v2 rendering code while removing v2's planner from the orchestration path.

## Principle

**Skills decide. Existing tools create. Code glues. GitHub renders and records.**
