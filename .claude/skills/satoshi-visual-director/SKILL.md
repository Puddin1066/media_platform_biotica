---
name: satoshi-visual-director
description: Choose the cheapest engaging visual primitive for every beat in an approved Satoshi Reel.
---

# Satoshi Visual Director

For each scripted beat choose the lowest-cost visual treatment that is still engaging.

Preference order:
1. real publication/researcher/institution evidence
2. typography, timeline, chart, or diagram
3. existing reusable Satoshi still or reaction
4. licensed/publicly usable historical or institutional image
5. generated still with camera movement
6. short generated video
7. talking avatar only when genuinely necessary

Target frequent cuts without requiring frequent expensive generation.

For the current renderer, emit only these production-safe primitives:
- beat kind: `evidence` or `host`
- visual type: `publication`, `typography`, `illustration`, or `host`

Use `publication` for researcher/institution/paper provenance. Use `typography` for timelines, comparisons, punchlines, and simplified diagrams. Use `illustration` as the placeholder for externally generated still/video assets until the renderer receives a dedicated asset URI. Use `host` sparingly.

For each beat specify:
- visual type
- source or generation prompt when needed
- concise on-screen text
- researcher/institution attribution when relevant
- whether motion can be created deterministically in Remotion
- whether an external media model is actually required

Never use lip sync merely because Satoshi is present.
