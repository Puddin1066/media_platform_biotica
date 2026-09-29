# Canonical Satoshi Conversation Pipeline

## Objective

Build one standalone production pipeline for Biotica Media that begins with an AI conversation and ends with a publishable Instagram Reel. Existing workflows remain intact as reference/legacy paths until this pipeline is proven.

The conversation is the creative source. The production pipeline must not reduce the input to a one-line topic and regenerate a generic explainer.

## Trigger contract

The operator has a free-form conversation with an AI. The conversation may be long, meandering, speculative, humorous, self-correcting, and only loosely related to men's health.

Production begins only after the operator gives an explicit trigger such as:

`Run the Satoshi script.`

The chat agent then materializes one canonical episode request containing the relevant conversation-derived material. The GitHub Action consumes that request; it does not need access to the full chat platform itself.

## Audience

Primary audience: people engaged with men's health, including clinicians, researchers, founders, investors, operators, and informed enthusiasts.

The editorial universe is intentionally broader than urology. Subjects may include fertility, sexual function, testosterone, pelvic pain, prostate disease, metabolism, cardiovascular risk, diagnostics, AI, biotech, environmental exposures, regulation, consumer health, and adjacent science/business stories when a defensible men's-health connection exists.

Current clinical framing supports this breadth: AUA guideline domains include male infertility, male sexual dysfunction, testosterone deficiency, chronic pelvic pain in men, prostate disease, and related urologic conditions. Recent sexual-medicine and reproductive-health literature also emphasizes the overlap among infertility, sexual dysfunction, hypogonadism, lifestyle, and broader health.

Reference anchors:
- https://helpdesk.auanet.org/hc/en-us/articles/40948838469143-Guidelines
- https://pubmed.ncbi.nlm.nih.gov/41504423/
- https://pubmed.ncbi.nlm.nih.gov/41901647/

## Canonical flow

1. **Conversation capture**
   - Preserve the relevant chat as source material.
   - Preserve strong natural phrasing, jokes, objections, analogies, corrections, and uncertainty.

2. **Editorial mining**
   - Rank candidate moments for:
     - surprise / interest
     - humor
     - insight
     - contradiction
     - memorability
     - evidence value
     - men's-health relevance
     - visual potential
     - narrative usefulness
   - Do not simply pick the most emotional or provocative lines.

3. **Thesis discovery**
   - Determine what the conversation was actually about after the full discussion.
   - Identify the central tension, strongest question, and most defensible takeaway.

4. **Claim graph**
   - Separate:
     - factual claims
     - opinions
     - hypotheses
     - jokes / rhetorical lines
     - analogies
     - objections
     - open questions
     - claims requiring verification

5. **Research and verification**
   - Use OpenAI web-enabled research to verify consequential claims, challenge weak assumptions, and add receipts.
   - Research is subordinate to the conversation: verify and enrich the user's reasoning rather than replacing it with a generic summary.

6. **Story architecture**
   - Build the episode after research, not before.
   - Default story beats:
     1. Hook
     2. What everyone thinks
     3. Why we think that
     4. The receipt
     5. The objection
     6. The weird part
     7. Competing explanations
     8. Men's-health connection
     9. Satoshi synthesis
     10. Button / callback
   - Beats may be omitted or merged when the story is stronger without them.
   - The objection must be the strongest intelligent counterargument, not a straw man.

7. **Hook generation**
   - Generate the hook only after the final narrative spine is known.
   - Prefer the strongest contradiction, curiosity gap, surprising consequence, or memorable joke discovered in the conversation.

8. **Timed script**
   - Produce a concise Satoshi monologue from the selected beats.
   - Preserve unusually strong operator phrasing when it is clearer or funnier than a rewrite.
   - Each beat becomes a first-class production object.

9. **Optional host-plate ingestion**
   - If the triggering conversation includes a new host video/plate, prefer it for that episode.
   - Validate media before any paid Runway work.
   - Persist accepted plate to Cloudflare R2.
   - If no new plate exists, use the configured default plate/avatar.

10. **Beat-matched visual generation**
    - Default visual source: low-cost OpenAI still images.
    - Generate visuals from the meaning of each beat, not merely topic keywords.
    - Prefer diagrams, documentary-style stills, symbolic visuals, and evidence cards appropriate to the spoken line.
    - Do not fabricate chart values, paper screenshots, clinical outcomes, logos, or identifiable real people.
    - Wikimedia Commons is fallback-only, not the canonical source.
    - Expensive generative video is exception-only.

11. **Host performance**
    - Use RunwayML for the moving Satoshi host / talking-head layer.
    - Runway is not the default B-roll generator.

12. **Overlay choreography**
    - Remotion controls the evidence window above/beside the host.
    - Still images may:
      - hold on a receipt
      - flip rapidly through 2-3 supporting images
      - slide / push / crossfade
      - use slow crop/zoom
      - pause for a joke or contradiction
    - Image changes are synchronized to beat timing.

13. **Composition**
    - Remotion combines:
      - moving host
      - narration/audio
      - beat-matched image overlays
      - captions
      - citations / source labels
      - Biotica/Satoshi branding
      - deterministic transitions

14. **Quality control**
    - Require:
      - valid video and audio streams
      - expected duration
      - no missing beat assets
      - no broken citations
      - no overlay/caption collisions
      - no unverified factual claims promoted as fact
      - public-media readiness before Meta handoff

15. **Cloudflare R2 persistence**
    - Persist host plate, generated assets as needed, final reel, and media manifest.
    - Final video must be anonymously fetchable over HTTPS before Instagram submission.

16. **Meta / Instagram publish**
    - Publishing is the terminal stage, not part of rendering.
    - Create the Reel container through the Meta/Instagram Graph integration.
    - Poll processing status.
    - Publish to the configured professional account.
    - Record post/container IDs, status, and analytics handle/ledger metadata.

17. **Feedback loop**
    - Later iterations may use retention, completion, saves, shares, and comments to improve hooks, beat timing, visual cadence, and endings.

## Canonical beat object

Each beat should carry enough information to keep script, evidence, and editing synchronized:

```json
{
  "beat_id": "b05",
  "role": "objection",
  "spoken_text": "...",
  "source_conversation_refs": ["m18", "m23"],
  "claim": "...",
  "claim_status": "verified",
  "citations": ["https://..."],
  "humor_score": 0.4,
  "insight_score": 0.9,
  "visual_intent": "Show the strongest counterexample without mocking it",
  "image_prompt": "...",
  "image_asset": "r2://...",
  "overlay_motion": "hold_then_flip",
  "duration_seconds": 4.2
}
```

## Provider responsibilities

| Provider | Canonical responsibility |
|---|---|
| OpenAI | conversation mining, research/verification, story architecture, script, beat-specific still images |
| RunwayML | moving host / performance only by default |
| Remotion | deterministic composition, captions, overlay choreography, transitions, final render |
| Cloudflare R2 | durable media storage and public final-media URL |
| Meta / Instagram | Reel container creation, processing, publish, post bookkeeping |

## Cost-control policy

1. OpenAI low-cost stills are the default overlay visual.
2. Remotion creates perceived motion from stills.
3. Runway spend is concentrated on the host.
4. Reuse cached assets when request/beat hashes have not changed.
5. Validate inputs and providers before paid work.
6. Persist successful intermediate paid assets so a downstream failure does not require regenerating them.

## Migration policy

This pipeline is built alongside existing workflows.

Do **not** delete or mutate legacy workflows in this PR.

After this path reliably produces complete episodes, a later cleanup PR can classify old workflows as:
- archived experiment
- reusable test fixture
- superseded production path
- retained utility

## Definition of done

The canonical pipeline is complete when one conversation-derived request can, in a single workflow execution or resumable staged execution:

1. validate the request,
2. produce a verified beat plan,
3. generate the final script,
4. ingest or select the host plate,
5. generate beat-matched OpenAI stills,
6. generate the Runway host performance,
7. render the full Remotion Reel,
8. pass QC,
9. persist final media to R2,
10. create a publish packet,
11. optionally publish through Meta/Instagram,
12. emit an auditable episode manifest tying every output back to the conversation-derived request and beat objects.
