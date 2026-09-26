# Mystery is the product

Audience hypothesis: men roughly 20–50 who are curious about their bodies,
sexuality, capability, appearance and futures will follow rigorous, emotionally
engaging science mysteries. Audience size, unmet demand and sponsor willingness
to pay remain hypotheses to validate, not established market facts.

## Sponsor-friendly editorial pillars

Biotica Media is not a generic wellness channel. Its editorial promise is:
**investigate the science, technology, incentives and bullshit shaping men's
health.** Every topic must earn its place by creating a clear audience reason to
watch and a credible men’s-health commercial context without allowing sponsor
fit to determine the scientific conclusion.

The canonical taxonomy and target publishing mix live in `content_pillars.json`:

- 25% Testosterone & Hormonal Optimization
- 20% Male Fertility & Reproductive Health
- 15% Sexual Function & Urology
- 15% Health-Maxxing: What Actually Works?
- 15% Men's Health Conspiracy Files
- 10% Frontier Men's Health Tech

Run `python3 content_strategy.py list` to inspect audience jobs, sponsor categories,
topic examples and prohibited shortcuts. Run `python3 content_strategy.py next
--history <published.json>` to select the most underrepresented pillar relative
to the target mix. The mix is an initial commercial/editorial hypothesis; actual
retention, shares, saves, follows, return viewers and qualified sponsor inquiries
should move the weights over time.

### Conspiracy Files

"Conspiracy" is a discovery frame, not a conclusion. A Conspiracy Files episode
must include: a provocative claim; why reasonable people suspect it; primary
receipts; the strongest counter-case; and one bounded verdict: **REAL PROBLEM**,
**PLAUSIBLE BUT UNPROVEN**, **MOSTLY INTERNET MYTH**, or **INSUFFICIENT EVIDENCE**.
Sponsor interest can never determine the verdict.

## Documented misconduct as the primary story lane

Prioritize men's-health stories in which both the health context and a specific
act of concealment, fraud, coordination or anticompetitive conduct have primary
records. The intake queue is `cases/documented-conduct-topics.json`; run
`python3 topic_queue.py list` or export a pending case with
`python3 topic_queue.py export --topic-id lupron-prostate-kickbacks --output outputs/lupron-case.json`.
The exported case can feed web-search drafting, but its claim remains pending
and its source is not cleared for model excerpt processing. A reviewer must
check the underlying documents, contrasting records, claim wording and reuse
rights before approving a script or any visual asset.

The legal status must travel with every short, podcast, newsletter and Reel:
**plea**, **affirmed liability**, **allegation resolved by settlement**, and
**observed financial incentive** are different statements. An indictment is
not a conviction; a settlement need not establish wrongdoing; a correlation is
not a secret agreement. The clip montage illustrates the specific sourced
story and cannot turn unrelated viral footage into evidence of conduct.

## Required episode brief (future production gate)

1. Anomaly: what demonstrably does not add up? Cite the evidence establishing it.
2. Personal stakes: why does this audience care?
3. Competing explanations: include alternatives, not a predetermined villain.
4. Discriminating test: what observation could change our view?
5. Payoff: what does this installment genuinely establish or clarify?
6. Open question: what remains unresolved, and what would help resolve it?

An episode may resolve a smaller question without resolving the season's mystery.
No invented contradictions, forced reversals, fabricated interviews or artificial
cliffhangers. An inconclusive result may justify an episode, or may warrant HOLD.

## Consistency and creative range

Maintain Satoshi Shkreli as an original, skeptical, witty on-camera host with
concrete metaphors, varied sentence lengths, legible source displays and explicit
uncertainty. Use original jokes about claims or situations, never patients or
bodies. The host-led satirical research format can use a desk setup, quick
visual cutaways and a timed corner inset; avoid reproducing any real presenter's
voice, catchphrases, signature jokes or distinctive performance. Encourage pleasure, ambition,
attraction, competence and wonder alongside concern; do not exploit insecurity.
Each format pins the same approved evidence and editorial revisions, but uses
its own pacing and structure. New evidence changes conclusions openly.

## Commercial validation

Measure topic/format experiments, viewing or listening completion, return visits,
voluntary subscriptions and actual sponsor inquiries. Record denominators and
sample sizes. Public view counts alone do not prove unmet demand or profitability.
Sponsor suitability is assessed separately from evidentiary judgments. No sponsor
may dictate a scientific conclusion or suppress a correction.

Prioritize these metrics for short-form iteration: 3-second hold, completion rate,
shares, saves, follows per 1,000 views, return viewers and qualified sponsor
inquiries. Sponsor categories in `content_pillars.json` are targeting metadata,
not endorsements and not evidence of willingness to buy.

## Implementation status

The content taxonomy and deterministic mix planner are implemented. Artistic
appeal, scientific truth, sponsor demand and whether a topic is genuinely
interesting still require empirical validation rather than being assumed from
the taxonomy.
