# Agentic podcast quality gate

The adaptive engine is **not canonical by default**.

Compare it against the existing whole-script podcast writer using the same:
- episode question;
- evidence packet;
- model tier;
- target runtime;
- editorial constraints.

Blind the outputs before review.

Score 1-5 on:
- listening pull;
- naturalness;
- coherence;
- evidence fidelity;
- speaker distinction;
- originality.

Promotion rule:
1. positive overall blinded score delta;
2. no reduction in evidence fidelity.

Deterministic diagnostics also flag:
- adjacent lexical repetition;
- excessive agreement streaks;
- absence of challenge/reversal;
- missing callback;
- missing resolution;
- evidence coverage;
- unresolved threads.

These diagnostics are warnings, not substitutes for editorial review.

Example:

```sh
python3 podcast_quality.py diagnose \
  --state outputs/podcast-agentic/example/conversation-state.json

python3 podcast_quality.py compare \
  --scorecard references/podcast-quality-scorecard.json
```
