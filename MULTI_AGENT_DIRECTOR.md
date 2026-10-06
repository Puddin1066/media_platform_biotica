# Satoshi multi-agent visual direction

The production unit is now a **candidate library**, not a single generated shot.

## Flow

```
researched script
  -> visual_director.py          semantic visual grammar
  -> asset_coverage.py           several candidates per beat
  -> generate/cache candidates   evidence + stills + selective motion
  -> multi_director.py           retention / credibility / comedy edits
  -> critic consensus            selected_edit + narrow retry requests
  -> Remotion                    deterministic execution
```

## Candidate policy

Each semantic beat can expose:

- real evidence/source material when a source exists;
- a zero-credit Remotion-native treatment;
- two or more generated still alternatives;
- selective generated motion for pattern interrupts, jokes, escalation and callbacks.

This gives downstream directors meaningful editorial choice without asking Runway
to generate the complete Reel.

Illustrations never become evidence. Exact numbers, charts, citations and labels
remain native Remotion layers or source-derived assets.

## Director tournament

Three deterministic baseline directors currently score the same pool:

1. **retention** — motion and pattern interruption;
2. **credibility** — evidence and explanatory native graphics;
3. **comedy** — visual metaphor and absurd contrast.

The critic chooses majority consensus, breaks ties toward credibility, and only
requests a paid regeneration for a specifically weak beat. The policy explicitly
forbids whole-episode regeneration.

These deterministic agents are intentionally simple. LLM directors can later
replace the scoring function while retaining the exact manifest contracts and
cost controls.

## Spend shape

The design favors many cheap alternatives and few motion clips. A normal six-slot
episode with two stills per slot and four motion candidates remains well below a
500-credit ceiling before retries. The remaining credits should be held for
targeted replacements identified after preview.

## Files

- `visual_director.py` — semantic visual intent and provider prompt grammar.
- `asset_coverage.py` — overcomplete candidate library.
- `multi_director.py` — competing editorial selections and critic.
- `test_multi_director.py` — offline contract tests.

The next integration step is to teach the existing preview orchestrator to
materialize the chosen candidate IDs and emit a Remotion edit-decision manifest.
