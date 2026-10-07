# Satoshi Producer v2

One input -> one episode manifest -> deterministic production.

## Command

```bash
python satoshi_v2/produce.py requests/satoshi_v2/example.json --publish
```

## Architecture

1. Planner: one reasoning/research call creates episode.json.
2. Voice: Clint TTS per beat.
3. Scene: one identity-locked Satoshi-in-world still.
4. Host: image-based Act Two only for short host beats.
5. Evidence: publication cards / typography / illustrations.
6. Render: one Remotion composition from render.json.
7. Persist: R2 by episode/content identity.
8. Publish: Instagram.

No production-state agents. GitHub Actions is only the runner.
