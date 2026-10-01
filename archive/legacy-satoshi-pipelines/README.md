# Legacy Satoshi Pipeline A/B archive

Archived October 1, 2026 after Satoshi Studio became the canonical production path.

This directory preserves the old monolithic GitHub Actions entrypoints and their last canonical request for historical reference only. They are intentionally stored outside `.github/workflows/` so GitHub Actions will not execute them.

Archived entrypoints:
- `satoshi-editorial.yml` — legacy Pipeline A editorial package workflow
- `satoshi-production.yml` — legacy Pipeline B package-consuming production workflow
- `current.json` — final `requests/satoshi_editorial/current.json` request snapshot

Do not use these files for new episodes. Use the modular Studio episode manifests and `studio-<module>.yml` workflows.

The Python modules `satoshi_editorial_pipeline.py` and `satoshi_production_pipeline.py` remain at repository root because current Studio modules reuse their helper/runtime functions. Their presence does not make the legacy A/B Actions active.
