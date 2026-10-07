---
name: satoshi-reel-producer
description: Turn a verified Satoshi research brief into an engaging 45-70 second evidence-led Reel production manifest.
---

# Satoshi Reel Producer

Create one 45-70 second vertical Reel around one thesis.

## Research provenance
Use web research before scripting. Prefer primary research and authoritative institutional sources. For each central source capture audience-useful provenance:
- paper/trial/source title
- journal or source and year
- 1-3 relevant researchers
- relevant institutions
- one memorable finding
- a clean public link only when useful

Do not put DOI strings, PubMed IDs, or formal bibliography clutter on screen unless they are specifically useful. **Show provenance, not bibliography.**

## Editorial rhythm
Default:
1. hook
2. setup
3. evidence/researcher
4. mechanism or technological change
5. complication/reframe
6. implication
7. memorable payoff

Use real researcher/institution attribution as a recurring engagement device. Name the people behind the work when that improves the story.

## Voice
Dry, intelligent, specific, slightly odd. Never generic wellness language.

## Visuals
Do not default to a talking avatar. Use voiceover plus rapid visual changes. Satoshi can appear as a short visual punctuation mark. Prefer real publication/researcher/institution cards, diagrams, historical imagery, typography, and a few high-value generated shots.

## Output contract
Return one complete episode JSON with:
- episode_id
- title
- topic
- scene
- sources
- beats
- caption
- hashtags

Each beat needs id, text, kind, and visual. Use kind "evidence" or "broll" by default; use "host" only when a short Satoshi appearance materially improves the beat.
