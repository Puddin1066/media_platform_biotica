"""Run a blinded rhetoric benchmark on real, source-anchored men's-health evidence packets.

This benchmark is intentionally separate from the earlier synthetic benchmark. Each case
contains named source material, concrete findings, a counter-case, and an editorial tension.
Both arms receive the exact same evidence packet; only the semantic arm receives retrieved
neutral rhetoric mechanics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from openai_models import model_for, reasoning_for
from semantic_rhetoric import (
    DIMENSIONS,
    _require_live,
    _response_text,
    _judge,
    build_index,
    retrieve,
    semantic_clusters,
)

REAL_EVIDENCE_BRIEFS = [
    {
        "id": "R01",
        "topic": "TRAVERSE: testosterone looked cardiovascularly noninferior on the primary endpoint while several adverse-event signals moved the other way",
        "source_name": "Lincoff et al., New England Journal of Medicine, 2023 — Cardiovascular Safety of Testosterone-Replacement Therapy",
        "source_url": "https://www.nejm.org/doi/10.1056/NEJMoa2215025",
        "receipts": [
            "5,246 men age 45-80 with hypogonadism and preexisting or high cardiovascular risk were randomized to transdermal testosterone gel or placebo.",
            "Primary MACE occurred in 7.0% on testosterone vs 7.3% on placebo; hazard ratio 0.96 (95% CI 0.78-1.17), meeting the trial's noninferiority criterion.",
            "Atrial fibrillation was reported in 3.5% vs 2.4%, acute kidney injury in 2.3% vs 1.5%, and nonfatal arrhythmia requiring intervention in 5.2% vs 3.3%.",
            "The paper says multiplicity was not adjusted for secondary endpoints, so those signals should not be treated as definitive causal findings on their own.",
        ],
        "tension": "The clean headline is 'TRT was heart-safe'; the receipts support a narrower statement: the prespecified MACE endpoint cleared noninferiority while some secondary safety signals still deserve attention.",
        "counter_case": "The trial was large and randomized, and the primary cardiovascular result was reassuring for the population and transdermal regimen actually studied.",
    },
    {
        "id": "R02",
        "topic": "Microplastics were found in every human testis sampled, but the fertility implication is much less settled than the headline",
        "source_name": "Hu et al., Toxicological Sciences, 2024 — Microplastic presence in dog and human testis",
        "source_url": "https://academic.oup.com/toxsci/article/200/2/235/7673133",
        "receipts": [
            "Researchers measured 12 polymer types in 23 human testes and 47 canine testes using pyrolysis-gas chromatography/mass spectrometry.",
            "Microplastics were detected in all sampled human and canine testes.",
            "Mean total microplastic concentration was 328.44 micrograms per gram in human tissue vs 122.63 micrograms per gram in canine tissue; polyethylene was the dominant polymer.",
            "Human samples could not establish a sperm-count relationship; sperm-count associations were evaluated in dogs, making causal claims about human infertility premature.",
        ],
        "tension": "The shocking part is real — plastic was measurable in every sampled human testis — but 'microplastics are causing male infertility' goes beyond what the human data showed.",
        "counter_case": "This was a small tissue study using stored postmortem human samples; detection and causation are not the same thing.",
    },
    {
        "id": "R03",
        "topic": "The global sperm-count decline is large enough to sound conspiratorial, but the meta-analysis cannot identify a single cause",
        "source_name": "Levine et al., Human Reproduction Update, 2022 — Temporal trends in sperm count",
        "source_url": "https://academic.oup.com/humupd/article/29/2/157/6824414",
        "receipts": [
            "The updated meta-analysis combined 223 studies and 288 estimates using semen samples collected from 1973 through 2018.",
            "Among unselected men across all continents, mean sperm concentration declined 51.6% between 1973 and 2018.",
            "The estimated annual percent decline was steeper after 2000: 2.64% per year vs 1.16% per year over the broader period.",
            "The analysis is observational and ecological across studies; it documents a trend but does not establish which exposures or behaviors caused it.",
        ],
        "tension": "A roughly halving of sperm concentration is the kind of number that fuels endocrine-disruptor, plastic, diet, heat, obesity, and technology theories — but the paper itself does not pick a culprit.",
        "counter_case": "Changes in study populations, laboratory methods, geography, abstinence time, and other covariates can complicate long-term semen-trend estimates even when meta-regression attempts to adjust for them.",
    },
    {
        "id": "R04",
        "topic": "A daily male contraceptive gel completed a multinational Phase IIb efficacy trial, but the public evidence still stops short of an approved male birth-control product",
        "source_name": "NICHD Contraceptive Development Program 2024 Annual Report — Nestorone/Testosterone Gel",
        "source_url": "https://annualreport.nichd.nih.gov/2024/blithe.html",
        "receipts": [
            "The Nestorone/testosterone gel combines a progestin that suppresses gonadotropins with testosterone replacement intended to preserve androgen-dependent functions.",
            "The Phase IIb couples trial was conducted across 9 US sites plus international sites in the UK, Chile, Sweden, Italy, Kenya, and Zimbabwe.",
            "The efficacy phase required men to suppress sperm production while couples relied on the gel for pregnancy prevention, followed by a recovery phase to assess return of sperm production.",
            "NICHD reported the Phase IIb trial completed in 2024 and said analysis of pregnancy prevention, safety, reversibility, and acceptability was still under way.",
        ],
        "tension": "Men have heard 'male birth control is five years away' for decades; this program is unusually far along, but completion of a Phase IIb trial is not the same thing as an approved product.",
        "counter_case": "The mechanism is established enough to support a large couples trial, yet the decisive efficacy, reversibility, adherence, safety, and regulatory questions still have to clear.",
    },
    {
        "id": "R05",
        "topic": "A smartphone home semen analyzer became a much more quantitative fertility tool — and the FDA clearance itself says it still cannot tell you whether you're fertile",
        "source_name": "FDA 510(k) K241628 — YO Home Sperm Test 3.0, cleared Nov. 29, 2024",
        "source_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K241628",
        "receipts": [
            "YO 3.0 is an over-the-counter smartphone-based semen analyzer for lay users that reports sperm concentration, total motility, progressive motility, motile sperm concentration, and progressively motile sperm concentration.",
            "In a 309-sample, three-site method-comparison study, correlations with the comparator system ranged from 0.88 to 0.94 across reported parameters.",
            "The system captures HD video and uses proprietary software algorithms to identify sperm and quantify concentration and movement-related parameters.",
            "The FDA-cleared indication explicitly says the test does not provide a comprehensive evaluation of a male's fertility status.",
        ],
        "tension": "The tech has crossed from a crude home screening gadget into multi-parameter quantitative semen analysis — while its own clearance draws a bright line between measuring semen and diagnosing fertility.",
        "counter_case": "Strong method correlation is useful analytical validation, but fertility depends on more than the semen parameters this device reports and on the female partner and couple context as well.",
    },
    {
        "id": "R06",
        "topic": "Oral minoxidil is booming as a convenient hair-loss alternative, but the first randomized male comparison did not show it was generally superior to topical minoxidil",
        "source_name": "Penha et al., JAMA Dermatology, 2024 — Oral Minoxidil vs Topical Minoxidil for Male Androgenetic Alopecia",
        "source_url": "https://jamanetwork.com/journals/jamadermatology/fullarticle/2817326",
        "receipts": [
            "Ninety men with androgenetic alopecia were randomized to oral minoxidil 5 mg daily or topical minoxidil 5% twice daily for 24 weeks; 68 completed the study.",
            "The primary hair-density comparisons did not show oral minoxidil was superior overall to topical minoxidil.",
            "Blinded photographic assessment favored oral minoxidil at the vertex: 70% improved vs 46%, a 24 percentage-point difference; frontal improvement was not significantly different.",
            "Hypertrichosis occurred in 49% of the oral group vs 25% of the topical group, and headache in 14% vs 2%.",
        ],
        "tension": "The pill is easier than rubbing solution on your scalp twice a day, which makes it commercially irresistible — but convenience and one favorable photographic endpoint are not the same as broad superiority.",
        "counter_case": "The trial was small, single-center, only 24 weeks, and had substantial dropout; it still supports oral minoxidil as a reasonable alternative for some men rather than a universal upgrade.",
    },
]


def evidence_text(brief: dict) -> str:
    receipts = "\n".join(f"- {x}" for x in brief["receipts"])
    return (
        f"SOURCE: {brief['source_name']}\n"
        f"SOURCE URL: {brief['source_url']}\n"
        f"RECEIPTS:\n{receipts}\n"
        f"TENSION: {brief['tension']}\n"
        f"STRONGEST COUNTER-CASE: {brief['counter_case']}"
    )


def script_prompt(brief: dict, mechanics: list[dict] | None) -> str:
    extra = ""
    if mechanics:
        selected = "\n".join(
            f"- {m['function']}: {m['mechanic']} | avoid: {m['avoid']}" for m in mechanics
        )
        extra = "\n\nOPTIONAL TRANSFERABLE STRUCTURAL MECHANICS:\n" + selected
    return (
        f"TOPIC: {brief['topic']}\n\n{evidence_text(brief)}\n\n"
        "Write a 90-120 word Satoshi Shkreli / Biotica Media short-form monologue for skeptical, technically minded men 25-50. "
        "The script must feel like an investigation with receipts, not a generic health summary. Name the publication, regulator, trial, institution, or technology naturally in the spoken copy. "
        "Use at least two concrete numbers or specific findings from the packet when available. Surface the tension or apparently conspiratorial/weird element early, then distinguish what the evidence actually proves from what people may infer. "
        "Include the strongest counter-case without deflating the hook. Do not invent any fact beyond this packet. Do not give individualized medical advice. "
        "End on a sharp implication or unresolved question. Do not mention rhetorical mechanics or Huberman."
        + extra
    )


def generate_candidate(brief: dict, mechanics: list[dict] | None, key: str) -> str:
    return _response_text(
        model_for("writing"),
        "Write original, evidence-forward Biotica Media copy in the Satoshi Shkreli brand voice. Prioritize named receipts, specificity, tension, and skeptical interpretation. Do not imitate any real creator or reuse distinctive phrasing.",
        script_prompt(brief, mechanics),
        key,
        reasoning_for("writing"),
    )


def run_real_benchmark(index: dict, top_k: int = 3) -> dict:
    key = _require_live()
    totals = {"none": {d: [] for d in DIMENSIONS}, "semantic": {d: [] for d in DIMENSIONS}}
    wins = {"none": 0, "semantic": 0, "tie": 0}
    trials = []
    for brief in REAL_EVIDENCE_BRIEFS:
        query = brief["topic"] + " " + brief["tension"] + " " + brief["counter_case"]
        selected = retrieve(index, query, top_k=top_k)
        baseline = generate_candidate(brief, None, key)
        semantic = generate_candidate(brief, selected, key)
        swap = int(hashlib.sha256(("real:" + brief["id"]).encode()).hexdigest(), 16) % 2 == 0
        a, b = (semantic, baseline) if swap else (baseline, semantic)
        labels = {"A": "semantic", "B": "none"} if swap else {"A": "none", "B": "semantic"}
        judge_brief = {"topic": brief["topic"], "evidence": evidence_text(brief)}
        judged = _judge(judge_brief, a, b, key)
        for blind in ("A", "B"):
            arm = labels[blind]
            for d in DIMENSIONS:
                totals[arm][d].append(float(judged[blind][d]))
        pref = judged["preferred"]
        wins["tie" if pref == "tie" else labels[pref]] += 1
        trials.append({
            "brief_id": brief["id"],
            "topic": brief["topic"],
            "evidence": evidence_text(brief),
            "source_name": brief["source_name"],
            "source_url": brief["source_url"],
            "retrieved": [{k: m[k] for k in ("id", "episode_id", "mechanic_index", "function", "mechanic", "score")} for m in selected],
            "baseline_script": baseline,
            "semantic_script": semantic,
            "blind_order": labels,
            "judge": judged,
        })
    means = {arm: {d: sum(vals) / len(vals) for d, vals in dims.items()} for arm, dims in totals.items()}
    overall = {arm: sum(means[arm].values()) / len(DIMENSIONS) for arm in means}
    return {
        "schema_version": 2,
        "briefs_are_synthetic": False,
        "evidence_policy": "fixed_real_source_anchored_packets",
        "arms": ["none", "semantic"],
        "dimensions": list(DIMENSIONS),
        "top_k": top_k,
        "means": means,
        "overall": overall,
        "semantic_delta": overall["semantic"] - overall["none"],
        "wins": wins,
        "trials": trials,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--top-k", type=int, default=3)
    args = p.parse_args()
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    index = build_index(Path(args.source_dir))
    clusters = semantic_clusters(index)
    benchmark = run_real_benchmark(index, top_k=args.top_k)
    (out / "real-evidence-benchmark.json").write_text(json.dumps(benchmark, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "mechanics": index["mechanic_count"],
        "semantic_clusters": len(clusters),
        "top_k": args.top_k,
        "delta": benchmark["semantic_delta"],
        "wins": benchmark["wins"],
    }, indent=2))


if __name__ == "__main__":
    main()
