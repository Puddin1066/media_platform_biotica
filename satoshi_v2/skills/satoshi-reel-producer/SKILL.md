---
name: satoshi-reel-producer
description: Research, script, and direct evidence-heavy Instagram Reels for the fictional Satoshi men's-health persona. Use whenever a topic, paper, clinical technology, men's-health development, biotech story, or scientific question needs to become a 45-70 second Reel. The output is the canonical episode JSON consumed by satoshi_v2. Favor primary research, sharp hooks, short visible host beats, evidence cutaways, dry humor, and a strong final payoff.
---

# Satoshi Reel Producer

Turn one topic brief into one production-ready Reel manifest. Do not manage provider state, GitHub Actions, Runway tasks, storage, or publishing. Those are deterministic production concerns handled downstream.

## Editorial objective

Make a smart viewer stop, understand one surprising technological or scientific idea, and remember one line afterward.

Satoshi should feel like a technically literate investor or operator explaining something strange to another smart person. He is curious, dry, skeptical, and occasionally absurd. Avoid generic influencer language, motivational phrasing, awareness-month language, and disclaimer-heavy scripts.

## Research rules

1. Search current sources when the topic depends on recent science, products, approvals, trials, or company pipelines.
2. Prefer primary publications over reviews, meta-analyses, press summaries, or secondary explainers.
3. For clinical claims, distinguish:
   - established standard of care,
   - approved but newer technology,
   - investigational technology,
   - speculative implication.
4. Preserve memorable user language when scientifically defensible.
5. Do not invent citations, DOI values, trial names, investigators, or statistics.

## Story selection

Choose one central thesis. Do not write a survey.

Good theses usually follow one of these patterns:
- a technology changed how clinicians see, target, measure, or treat disease;
- an old clinical assumption was replaced by a better interface or workflow;
- a highly cited primary paper changed downstream practice;
- an approved technology created the platform for a more radical next-generation technology;
- the mechanism is stranger than the headline.

Prefer a hook that is one of:
- contrarian reframe,
- surprising data/stat lead,
- story opening,
- painfully specific observation,
- technological before/after.

The hook should earn attention in the first 2-3 seconds without clickbait.

## Beat architecture

Target 45-70 seconds and roughly 110-160 spoken words.

Use 5-8 beats total.

A strong default rhythm:
1. Hook / thesis
2. Historical or clinical setup
3. Primary evidence receipt
4. Mechanism or technology explanation
5. Complication / limitation
6. Next-generation technology
7. Payoff

Do not keep Satoshi visible continuously.

Host beats are for:
- hook,
- joke,
- thesis,
- correction,
- final payoff.

Evidence-heavy lines should usually play over:
- publication cards,
- simple diagrams,
- typography,
- technology imagery,
- mechanism visuals.

Visible Satoshi performances should be short. Prefer host lines around 8-15 words. Downstream production may let narration continue after the visible avatar cuts away.

## Scene direction

Create one coherent episode-world scene for Satoshi.

Requirements:
- seated, leaning, inspecting something, or otherwise physically anchored;
- waist-up or half-body;
- topic-relevant environment;
- natural adult proportions;
- no generic standing presenter;
- no suit by default;
- one or two useful props only;
- environment should help the joke or thesis.

Examples:
- pill-land set for placebo ritual;
- nuclear-medicine control room for PSMA therapy;
- fertility lab or sauna control room for heat/sperm topics;
- abandoned arcade for game-related stories.

## Evidence design

Publication visuals may cite one or more publication IDs.

Use the first publication as the primary on-screen receipt. Additional IDs are supporting evidence.

For every primary paper include, when available:
- id
- title
- authors or lead author
- journal
- year
- DOI
- source URL
- one-sentence finding

Do not make the paper card carry more text than a viewer can scan quickly.

## Quality checks before output

Score the draft internally on:
- hook strength,
- specificity,
- scientific grounding,
- differentiation,
- pacing,
- shareable line,
- visual variety,
- ending quality.

If any dimension is obviously weak, revise before returning the manifest.

The strongest standalone line should be something a viewer could screenshot and understand without the rest of the Reel.

## Output contract

Return one complete JSON object only. No markdown and no prose outside JSON.

Required top-level fields:

{
  "episode_id": "stable-slug",
  "title": "...",
  "topic": "...",
  "scene": {
    "environment": "...",
    "wardrobe": "...",
    "framing": "..."
  },
  "publications": [],
  "beats": []
}

Each beat:

{
  "id": "b01",
  "kind": "host" | "evidence",
  "text": "exact spoken words",
  "visual": {
    "type": "host" | "publication" | "typography" | "illustration",
    "publication_ref": "paper_id" | ["paper_id","supporting_id"],
    "screen_text": "optional"
  }
}

Keep the JSON compact and syntactically complete.

## Production boundary

Once this JSON is emitted, stop making editorial decisions.

Downstream software owns:
- voice generation,
- Satoshi scene-image generation,
- lip-sync/avatar generation,
- Remotion assembly,
- R2 persistence,
- Instagram publishing.

The episode manifest is the handoff contract.
