# Agentic podcast runtime

`podcast_agents.py` implements the adaptive long-form runtime.

- **Monologue:** producer + Satoshi only.
- **Dialogue:** producer + Satoshi + independently prompted counterpart.
- Speaking agents never share private persona prompts.
- Both speaking agents receive the same approved evidence packet.
- Producer decisions and turns are persisted separately.
- Generation is sequential and stateful, not one model writing both sides at once.
- Every output remains review-required.

Dry-run example:

```sh
python3 podcast_agents.py \
  --config /private/agent-config.json \
  --evidence /private/evidence-packet.json \
  --episode-id sauna-fertility \
  --question "Does repeated sauna exposure meaningfully affect male fertility?"
```

For live generation set `OPENAI_LIVE_ENABLED=true` and `OPENAI_API_KEY` privately.

The existing whole-script podcast writer remains the comparison baseline.
