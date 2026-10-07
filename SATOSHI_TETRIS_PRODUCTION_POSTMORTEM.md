# Satoshi Tetris Video — Production Method, Failure Analysis, and V2 Direction

## Purpose

This document records the exact production method used for the successful Tetris / latent-digital-therapeutics Satoshi video so future iterations improve the creative quality without losing the production reliability that was achieved.

The key conclusion is that **the pipeline worked technically, but the direction did not work creatively**.

The system successfully:
- generated a usable library of original visual assets,
- selected and assembled them,
- created narration,
- generated a host/avatar performance,
- rendered a finished vertical MP4,
- and did so with a bounded, explicit media-generation budget.

The weaknesses were not primarily infrastructure failures. They were:
- weak comedic direction,
- overly academic copy,
- poor prosody,
- the wrong voice,
- an unconvincing talking-avatar performance,
- and insufficiently explicit character direction.

The next version should therefore **preserve the asset-generation and Remotion assembly architecture while replacing the performance/directorial layer**.

---

# 1. Episode Produced

Topic:

> Latent digital therapeutics: Tetris and trauma-related intrusive memories

Core thesis:

> Existing consumer software may contain cognitive or behavioral mechanisms that are worth clinically validating for narrow therapeutic uses. Tetris is an evidence-backed example of the broader concept.

The final approximately 30-second episode used:
- a generated Satoshi host/avatar,
- synthetic narration,
- generated Runway B-roll,
- native Remotion typography/captions,
- an evidence-card treatment,
- and a final Remotion render.

---

# 2. Exact Production Method Used

## Step 1 — Lock the topic and thesis

The episode request lived in:

`requests/satoshi/current.json`

The request specified:
- topic,
- core thesis,
- claims to verify,
- scientific caveats,
- candidate hooks,
- visual ideas,
- host mode,
- and the target OpenAI model.

The important editorial guardrail was:

> “The important question is not whether a game is engaging. The question is whether the mechanic is doing causal therapeutic work.”

This topic definition was strong and should be retained as the starting point for future episodes.

---

## Step 2 — Freeze a Runway prompt manifest

Instead of asking one model to “make the video,” the visual-production task was decomposed into independent media jobs.

The manifest was stored at:

`production_specs/tetris_runway_parallel.json`

It contained explicit fields for each job:
- job ID,
- media type,
- purpose,
- Runway endpoint,
- model,
- prompt,
- duration/output count,
- and estimated credit cost.

The first-pass batch contained:

| Asset type | Model | Output |
|---|---|---|
| Hero motion | Seedance 2.5 | 1 × 4-second clip |
| Motion coverage | WAN 3 | 3 × 5-second clips |
| Still coverage | Muse Image | 10 stills across 4 requests |

Estimated first-pass spend:

**165 Runway credits**

This was successful because the system generated an overcomplete asset library before editing rather than forcing one monolithic video generation.

### Successful principle

> **Do not ask Runway to make the finished video. Ask Runway to make expensive visual ingredients. Let Remotion make the video.**

This principle should remain canonical.

---

## Step 3 — Submit the Runway jobs in parallel

The batch was executed by:

`runway_parallel_batch.py`

The corresponding GitHub Action was:

`.github/workflows/runway-parallel-satoshi.yml`

The runner:
1. validated every request against the current Runway operation schema,
2. verified the aggregate spend against the declared credit ceiling,
3. checked account credit balance,
4. assigned stable request IDs,
5. submitted all independent jobs concurrently,
6. prohibited automatic retries,
7. persisted results and provider-task state.

All 8 generation requests succeeded.

This proved that **parallel independent generation is a reliable production primitive**.

---

# 3. Visual Assets Actually Produced

The first pass generated 14 usable outputs:

### Motion
1. Prescription bottle → geometric puzzle blocks
2. Intrusive-memory / visuospatial-competition metaphor
3. Consumer-software → clinical-testing / repurposing metaphor
4. Engagement-vs-efficacy split-path metaphor

### Stills
- host/world concepts,
- prescription-game concepts,
- visuospatial-memory concepts,
- latent-therapy discovery concepts.

The hero prescription-bottle clip and intrusive-memory clip were the strongest results.

The weakest recurring issue was that some stills looked like **AI-generated infographics**, which reduced credibility.

### Lesson

Generated imagery should be used for:
- metaphor,
- absurdity,
- atmosphere,
- character moments,
- visual jokes,
- and transitions.

Generated imagery should **not** be used to impersonate:
- charts,
- papers,
- evidence receipts,
- trial results,
- or factual scientific graphics.

Those should be native Remotion layers or authentic source material.

---

# 4. Human/Editorial Asset Review

The generated media was manually inspected and ranked.

The selection was written into:

`production_specs/tetris_edit_decision.json`

The first EDL selected:
- the hero prescription-bottle clip,
- the memory-mechanism clip,
- the software-repurposing clip,
- the engagement-vs-efficacy clip,
- two supporting stills,
- and a native Remotion evidence slot.

This was a strong move.

The edit-decision-list approach should remain explicit and inspectable.

---

# 5. First Remotion Assembly

The direct visual-only render path was built with:

`direct_tetris_remotion.py`

and the Remotion composition:

`DirectTetrisEpisode`

The corresponding workflow was:

`.github/workflows/render-direct-tetris.yml`

This produced a technically correct 30-second visual sequence.

However, the first cut had:
- no Satoshi,
- no narration,
- no finished performance layer.

It should be understood as a **pipeline proof**, not a finished episode.

---

# 6. Final Script Used

The final script was defined in:

`production_specs/tetris_satoshi_final.json`

The script was:

> What if the next digital therapeutic already sold a hundred million copies?
>
> Tetris has been tested after trauma because its visuospatial demands may compete with intrusive visual memories.
>
> Randomized studies found fewer later intrusions in some settings.
>
> That does not make Tetris a PTSD treatment.
>
> It makes the business question interesting: how many ordinary games already contain a therapeutic mechanism? The important question is not whether a game is engaging. It’s whether the mechanic is doing causal therapeutic work.

The script was scientifically disciplined but creatively underpowered.

### What was good
- Strong central thesis
- Clear opening question
- Appropriate scientific limitation
- Commercial implication
- Good closing intellectual proposition

### What was weak
- Too declarative
- Too symmetrical in sentence structure
- Too academic
- No character reaction
- No surprise escalation
- No comedic contrast
- No rhetorical interruption
- No short-line rhythm
- No strong “Satoshi point of view”

The script reads like a polished abstract rather than a personality-driven short.

---

# 7. Narration Method Used

Narration was generated as five separate beats:
- opening,
- explanations,
- evidence,
- limits,
- next_test.

The existing narration machinery in:

`episode.py`

submitted the beats to Runway TTS and later assembled them into one WAV using:

`speech_timing.py`

The voice used was the configured Runway preset:

**Vincent**

The resulting narration was technically valid and frame-timed.

It was creatively wrong.

---

# 8. Prosody Failure

The narration suffered from:
- generic corporate pacing,
- insufficient sentence-final drops,
- inadequate deadpan timing,
- weak micro-pauses,
- excessive “explainer” cadence,
- no sense that the speaker was amused or skeptical,
- and no meaningful tempo changes.

The problem was not only the voice model.

The script itself failed to provide enough prosodic structure.

A voice model cannot create great comic timing from five similar declarative paragraphs.

Future scripts should intentionally contain:
- one- to five-word reaction sentences,
- abrupt line breaks,
- commas and em dashes used as performance instructions,
- rhetorical reversals,
- pause-worthy punch lines,
- conversational fragments,
- and alternation between fast explanatory passages and short deadpan reactions.

Example shape:

> “And here’s the weird part.
>
> Tetris.
>
> Yes. Tetris.”

That gives the TTS model usable prosodic geometry.

---

# 9. Host / Avatar Method Used

The final production script was:

`direct_satoshi_final.py`

The final GitHub workflow was:

`.github/workflows/render-final-satoshi-tetris.yml`

This workflow:
1. downloaded the already-generated visual asset batch,
2. generated narration,
3. assembled a single narration WAV,
4. invoked the configured Runway custom avatar,
5. generated a host video aligned to that narration,
6. placed the avatar underneath the edit,
7. used B-roll to cover portions of the narration,
8. added captions and evidence treatment in Remotion,
9. rendered the final MP4.

This technically worked.

---

# 10. Why the Host Looked Wrong

The avatar generation was effectively a **talking-head performance derived from a fixed identity/reference**.

Even though it was generated through Runway's avatar system rather than simply replaying an old cycling plate, aesthetically it behaved like a plate-driven talking avatar.

The failure modes were:
- uncanny lip movement,
- limited facial acting,
- an impression of “AI presenter” rather than “character,”
- insufficient cinematic variation,
- weak continuity with the generated B-roll,
- and too much visual attention placed on mouth synchronization.

This is not the desired Satoshi format.

---

# 11. Critical V2 Character Decision

Future Satoshi episodes should **not begin with the user as the host identity**.

Instead, Satoshi should become an intentionally designed fictional character.

The preferred direction is:

> **A realistic-looking fictional person designed specifically to embody the Satoshi Shkreli persona.**

The character should be generated from scratch and should not resemble a real person closely enough to create identity confusion.

### Desired broad character traits

Satoshi should read visually as:
- male,
- approximately 30s–40s,
- intelligent,
- slightly disheveled but expensive-looking,
- biotech / hedge-fund / founder-adjacent,
- dry and skeptical,
- comfortable in a lab, studio, conference room, gym, or investor setting,
- expressive enough for reaction shots,
- not conventionally “AI influencer” polished.

Possible visual archetype:

> A biotech founder crossed with a cynical financial analyst and an exhausted science journalist.

The goal is not “handsome presenter.”

The goal is **recognizable character**.

---

# 12. V2: Do Not Make the Character Lip-Sync by Default

The strongest design change is:

> **Satoshi should be the visual protagonist without necessarily being visibly speaking.**

Narration should usually remain voiceover.

Generated Satoshi scenes should therefore include:
- reaction shots,
- silent looks to camera,
- walking shots,
- gestures,
- handling props,
- visual jokes,
- observing scientific absurdities,
- interacting with generated environments,
- and recurring visual callbacks.

Examples:
- Satoshi staring skeptically at a prescription bottle dispensing puzzle blocks.
- Satoshi in a fake biotech lab watching generic game controllers move down a clinical-trial conveyor belt.
- Satoshi holding a clipboard while an absurd “software repurposing” experiment happens behind him.
- Satoshi looking directly at camera after an overconfident digital-health claim.
- Satoshi silently pressing a large red “HYPOTHESIS” stamp.

The narration can continue uninterrupted while those scenes play.

This avoids the weakest element of the previous video: artificial mouth animation.

---

# 13. V2 Character Creation Process

The character should be created once and then reused consistently.

## Stage A — Character design

Generate a grid of realistic fictional Satoshi candidates.

Evaluate:
- face memorability,
- age,
- wardrobe,
- hairstyle,
- comedic expressiveness,
- ability to read as biotech/finance/science,
- ability to work in both serious and absurd scenes.

Select one canonical identity.

## Stage B — Character reference pack

Create a small reference library:
- neutral frontal portrait,
- three-quarter portrait,
- full-body standing,
- seated studio pose,
- skeptical expression,
- amused expression,
- exhausted expression,
- serious evidence-reading expression.

These become reference inputs for future generation models.

## Stage C — Character bible

Store explicit identity rules:
- approximate age,
- facial structure,
- hair,
- wardrobe palette,
- accessories,
- mannerisms,
- framing conventions,
- environments,
- expressions,
- prohibited drift.

The character bible should live in the repo and be consumed by every Satoshi prompt.

## Stage D — Reusable visual references

Persist approved character images to durable storage and reference them during future image/video generations.

The system should reject Satoshi shots that visibly drift from the canonical identity.

---

# 14. Voice V2

The next episode should not simply select another pleasant narrator.

The system should audition voices specifically for:

> **dry intellectual sarcasm with conversational scientific credibility.**

The evaluation sample should be one fixed 10–15 second paragraph containing:
- a factual sentence,
- a short surprise sentence,
- a deadpan joke,
- and a serious correction.

Example audition text:

> “Digital health spent years trying to put medicine inside video games. Which is impressive, because Tetris may have accidentally gone the other direction. No, it does not treat PTSD. The actual finding is narrower — and much more interesting.”

Audition several voices against exactly the same text.

Score them for:
- dry delivery,
- sentence-final control,
- conversational realism,
- credibility,
- comedic timing,
- absence of “advertisement voice,”
- absence of exaggerated influencer enthusiasm.

The winning voice should then become part of the Satoshi identity.

---

# 15. Script V2

Future scripts should use a repeatable micro-structure.

Recommended pattern:

1. **Contradiction / hook**
2. **Unexpected reveal**
3. **Satoshi reaction**
4. **Scientific evidence**
5. **Comedic interpretation**
6. **Explicit caveat**
7. **Commercial or strategic consequence**
8. **Strong closing callback**

Example conceptual rhythm:

> Digital therapeutics usually start with a disease and build a game.
>
> Tetris may have done it backward.
>
> Which is mildly inconvenient if your startup just raised $80 million to invent blocks.
>
> Researchers have actually tested brief visuospatial gameplay after trauma...
>
> [evidence]
>
> No — Tetris is not a PTSD treatment.
>
> But it raises a much better question:
>
> How many therapeutic mechanisms are already hiding inside software people actually want to use?

This is much closer to the desired persona than the previous abstract-style script.

---

# 16. Canonical V2 Pipeline

The next production architecture should be:

```
TOPIC / PAPER / IDEA
        ↓
RESEARCH + CLAIM RECEIPTS
        ↓
SATOSHI SCRIPT
  - science
  - joke beats
  - reactions
  - prosody
        ↓
LOCK NARRATION SCRIPT
        ↓
VOICE AUDITION / CANONICAL SATOSHI VOICE
        ↓
MASTER NARRATION WAV
        ↓
DIRECTOR SHOT MANIFEST
        ↓
PARALLEL GENERATION
  ├─ Satoshi character scenes
  ├─ metaphor scenes
  ├─ absurd visual jokes
  ├─ transitions
  └─ alternate coverage
        ↓
REAL EVIDENCE ASSETS
        ↓
ASSET REVIEW / RANKING
        ↓
EXPLICIT EDL
        ↓
REMOTION
  - captions
  - citations
  - charts
  - timing
  - punch-ins
  - cut rhythm
        ↓
MP4
```

The key sequencing change is:

> **Narration and character direction should be locked before media generation.**

The previous workflow generated good media ingredients before the final comedic/performance direction had been established.

That made the editor responsible for solving a writing problem with footage.

---

# 17. What Should Remain Unchanged

The following parts worked and should not be discarded:

### Keep
- prompt manifests,
- parallel provider calls,
- bounded concurrency,
- explicit media budgets,
- durable task records,
- no automatic retries,
- overcomplete asset generation,
- asset review before editing,
- explicit EDL,
- Remotion as deterministic assembler,
- native captions,
- native evidence cards,
- real evidence rather than synthetic papers,
- separation between expensive generative assets and cheap editing.

### Replace
- generic TTS voice,
- academic script cadence,
- user-derived talking avatar,
- long visible lip-sync segments,
- host-as-news-anchor framing,
- weak comedic direction,
- generated science-infographic imagery.

---

# 18. Primary Lesson

The Tetris experiment demonstrated that the production infrastructure is no longer the main problem.

The remaining problem is **direction**.

The next system does not need dramatically more agents or orchestration.

It needs:
1. a well-defined fictional Satoshi character,
2. a canonical voice,
3. a stronger comedic writing grammar,
4. prosody-aware scripting,
5. character-driven visual prompts,
6. and a director that thinks in reactions, reveals, and callbacks rather than merely “coverage.”

The technical production skeleton is good enough to build on.

The goal of V2 is therefore not a new pipeline.

It is:

> **the same reliable pipeline with a much better performer, writer, and director.**
