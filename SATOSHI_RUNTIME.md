# Canonical Satoshi Runtime

There are exactly two supported operator runtimes:

1. **Satoshi Preview** — same story, Clint voice, Satoshi identity, evidence/card system,
   library lookup, candidate coverage, director tournament, realism rules, and Remotion edit.
   It favors reusable assets and lower-cost still materialization. It never publishes.
2. **Satoshi Production** — the same engine and episode contract. It permits fuller AI/motion
   materialization and higher-quality assets. Publication remains an explicit opt-in.

Both call `.github/workflows/satoshi-runtime.yml`, which calls `satoshi_runtime.py`,
which calls the single engine `satoshi_supervisor.py`.

Canonical episode timing:
- target: 55 seconds
- preferred range: 52–58 seconds
- hard maximum: 60 seconds
- spoken target: 115–145 words
- meaningful visual change: roughly every 2–4 seconds

Canonical editorial sequence:
hook → reveal → mechanism/context → evidence receipt → Satoshi reaction/interpretation →
caveat → consequence → callback.

Older Tetris, Studio-module, audition, acceptance, and direct-render workflows are development
tools or historical experiments. They are not alternative Satoshi runtimes.
