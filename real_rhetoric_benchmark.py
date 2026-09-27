"""Blind benchmark for perspective-driven, source-anchored Satoshi shorts.

The benchmark asks whether retrieved neutral rhetoric mechanics improve a publishable
investigation, not whether a model can compress an abstract. Both arms get the same
fixed research packet. The semantic arm alone gets retrieved structural mechanics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from corpus_embeddings import _openai_json
from openai_models import model_for, reasoning_for
from semantic_rhetoric import (
    _require_live,
    _response_text,
    build_index,
    retrieve,
    semantic_clusters,
)

RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
PERSPECTIVE_DIMENSIONS = (
    "hook_strength",
    "perspective_strength",
    "evidence_selectivity",
    "interpretive_value",
    "counter_case_quality",
    "audience_curiosity",
    "publishability",
)

REAL_EVIDENCE_BRIEFS = [
    {
        "id": "R01",
        "topic": "What TRAVERSE actually proved about testosterone cardiovascular safety",
        "source_name": "Lincoff et al., New England Journal of Medicine, 2023 — Cardiovascular Safety of Testosterone-Replacement Therapy",
        "source_url": "https://www.nejm.org/doi/10.1056/NEJMoa2215025",
        "anchor_receipts": [
            "5,246 men with hypogonadism and preexisting or high cardiovascular risk were randomized to testosterone gel or placebo.",
            "Primary MACE was 7.0% on testosterone vs 7.3% on placebo; HR 0.96, meeting noninferiority.",
            "Atrial fibrillation, acute kidney injury, and intervention-requiring arrhythmia were numerically higher on testosterone, but secondary endpoints were not multiplicity-adjusted.",
        ],
        "context_sources": [
            {
                "name": "FDA, Feb. 28, 2025 — class-wide testosterone labeling changes",
                "url": "https://www.fda.gov/drugs/drug-alerts-and-statements/fda-issues-class-wide-labeling-changes-testosterone-products",
                "fact": "After reviewing TRAVERSE, FDA removed boxed-warning language about increased adverse cardiovascular outcomes while separately requiring blood-pressure warnings based on ambulatory blood-pressure studies.",
            }
        ],
        "thesis_options": [
            "The victory-lap headline flattened a much narrower safety result.",
            "Safety narratives change depending on which endpoint becomes the headline.",
            "TRAVERSE is legitimately reassuring without being a blanket cardiovascular absolution for testosterone.",
        ],
        "counter_case": "The large randomized primary cardiovascular result was genuinely reassuring for the population and transdermal regimen studied.",
    },
    {
        "id": "R02",
        "topic": "Microplastics in human testes: disturbing detection versus proof of fertility harm",
        "source_name": "Hu et al., Toxicological Sciences, 2024 — Microplastic presence in dog and human testis",
        "source_url": "https://academic.oup.com/toxsci/article/200/2/235/7673133",
        "anchor_receipts": [
            "Microplastics were detected in all 23 sampled human testes; polyethylene was the dominant polymer.",
            "The human tissue study could not establish a sperm-count relationship, so it did not prove that microplastics cause human infertility.",
        ],
        "context_sources": [
            {
                "name": "Multi-site human study, 2024 — mixed microplastic exposure and sperm dysfunction",
                "url": "https://pubmed.ncbi.nlm.nih.gov/39342804/",
                "fact": "A separate multi-site observational study found microplastics in semen and urine and reported associations between higher mixed exposure and poorer semen parameters; association still does not establish causation.",
            }
        ],
        "thesis_options": [
            "The unsettling fact is how ubiquitous the exposure looks; the causal fertility story remains unfinished.",
            "Microplastic headlines are outrunning the human causal evidence.",
            "The signal is strong enough to investigate aggressively and too weak to declare a fertility culprit.",
        ],
        "counter_case": "The testis study was small and observational; finding material in tissue is not equivalent to showing that it damaged fertility.",
    },
    {
        "id": "R03",
        "topic": "The sperm-count decline is dramatic; the culprit is still an open question",
        "source_name": "Levine et al., Human Reproduction Update, 2022/2023 — Temporal trends in sperm count",
        "source_url": "https://pubmed.ncbi.nlm.nih.gov/36377604/",
        "anchor_receipts": [
            "The meta-analysis combined 223 studies and reported a 51.6% decline in mean sperm concentration among unselected men from 1973 to 2018.",
            "The estimated annual decline was steeper after 2000, but the analysis cannot identify a single causal exposure.",
        ],
        "context_sources": [
            {
                "name": "Hu et al., Toxicological Sciences, 2024 — microplastics in human testes",
                "url": "https://pubmed.ncbi.nlm.nih.gov/38745431/",
                "fact": "Microplastics have now been directly measured in human testicular tissue, making environmental-exposure hypotheses more concrete without proving they explain the decades-long sperm-count trend.",
            }
        ],
        "thesis_options": [
            "The alarming trend is better established than any single explanation for it.",
            "The real mystery is not whether sperm counts moved, but why competing causal stories remain unresolved.",
            "A giant population-level signal creates fertile ground for conspiracy precisely because causal attribution is weak.",
        ],
        "counter_case": "Long-term semen meta-analyses remain vulnerable to changes in populations, laboratory methods, geography, abstinence time, and other study-level differences.",
    },
    {
        "id": "R04",
        "topic": "Male contraceptive gel: technically far along, commercially still not here",
        "source_name": "NICHD Contraceptive Development Program 2024 Annual Report — Nestorone/Testosterone Gel",
        "source_url": "https://annualreport.nichd.nih.gov/2024/blithe.html",
        "anchor_receipts": [
            "A multinational Phase IIb couples trial tested daily Nestorone/testosterone gel while couples relied on it for pregnancy prevention after sperm suppression.",
            "NICHD reported the Phase IIb trial completed in 2024, with pregnancy prevention, safety, reversibility, and acceptability analyses still under way.",
        ],
        "context_sources": [
            {
                "name": "ClinicalTrials.gov — Nestorone/Testosterone male contraceptive gel development program",
                "url": "https://clinicaltrials.gov/study/NCT03452111",
                "fact": "The program is a real late-stage contraceptive-development effort rather than a preclinical concept, but trial completion is still several regulatory and commercialization steps away from an approved product.",
            }
        ],
        "thesis_options": [
            "Male birth control may be scientifically closer than its decades-long 'five years away' reputation suggests.",
            "The recurring delay is now less about whether sperm suppression works and more about translation, reversibility, adherence, regulation, and commercialization.",
            "Phase IIb completion is a meaningful milestone that should not be confused with an imminent pharmacy product.",
        ],
        "counter_case": "The mechanism is established enough for a couples efficacy trial, but efficacy, reversibility, adherence, safety, manufacturing, and regulatory questions still matter.",
    },
    {
        "id": "R05",
        "topic": "A smartphone semen analyzer can quantify sperm surprisingly well without diagnosing fertility",
        "source_name": "FDA 510(k) K241628 — YO Home Sperm Test 3.0, cleared Nov. 29, 2024",
        "source_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID=K241628",
        "anchor_receipts": [
            "YO 3.0 reports several semen parameters from smartphone-captured video and proprietary analysis; method-comparison correlations ranged from 0.88 to 0.94.",
            "Its FDA-cleared indication explicitly says it does not provide a comprehensive evaluation of a man's fertility status.",
        ],
        "context_sources": [
            {
                "name": "AUA/ASRM Male Infertility Guideline",
                "url": "https://www.auanet.org/documents/guidelines/pdf/male-infertility-guideline.pdf",
                "fact": "The guideline treats semen analysis as an important component of male evaluation but says semen-analysis results generally cannot precisely distinguish fertile from infertile men and that couple-level evaluation matters.",
            }
        ],
        "thesis_options": [
            "Consumer fertility technology is becoming lab-like faster than fertility itself is becoming reducible to a score.",
            "Better measurement can create false diagnostic certainty if the boundary between semen quality and fertility disappears in marketing.",
            "The FDA clearance is interesting partly because it draws the line the product category is tempted to blur.",
        ],
        "counter_case": "Quantitative home testing can still lower friction and provide useful semen information even though it cannot diagnose couple-level infertility by itself.",
    },
    {
        "id": "R06",
        "topic": "Why oral minoxidil is popular even though superiority over topical minoxidil is not established",
        "source_name": "Penha et al., JAMA Dermatology, 2024 — Oral Minoxidil vs Topical Minoxidil for Male Androgenetic Alopecia",
        "source_url": "https://jamanetwork.com/journals/jamadermatology/fullarticle/2817326",
        "anchor_receipts": [
            "In a randomized 24-week male trial, oral minoxidil 5 mg daily was not superior overall to topical 5% minoxidil twice daily on the primary hair-density comparisons.",
            "Oral therapy was easier to take and had a favorable vertex photographic endpoint, but hypertrichosis and headache were more common.",
        ],
        "context_sources": [
            {
                "name": "FDA LONITEN (oral minoxidil) label",
                "url": "https://www.accessdata.fda.gov/drugsatfda_docs/label/2015/018154s026lbl.pdf",
                "fact": "Oral minoxidil is an old systemic antihypertensive with potentially serious cardiovascular adverse effects; using low-dose oral minoxidil for hair loss is an off-label repurposing story, not simply a more convenient formulation of the topical hair product.",
            }
        ],
        "thesis_options": [
            "Convenience may be driving oral minoxidil's cultural momentum faster than superiority evidence.",
            "A systemic blood-pressure drug quietly becoming a beauty treatment is the more interesting story than another hair-count comparison.",
            "The randomized evidence supports an alternative for some men, not an automatic upgrade over topical treatment.",
        ],
        "counter_case": "The trial was small and short, and oral minoxidil may still be a reasonable alternative for men who cannot tolerate or adhere to topical treatment.",
    },
]


def evidence_text(brief: dict) -> str:
    anchors = "\n".join(f"- {x}" for x in brief["anchor_receipts"])
    context = "\n".join(
        f"- {x['name']} | {x['fact']} | {x['url']}" for x in brief.get("context_sources", [])
    ) or "- none"
    theses = "\n".join(f"- {x}" for x in brief["thesis_options"])
    return (
        f"ANCHOR SOURCE: {brief['source_name']}\n"
        f"ANCHOR URL: {brief['source_url']}\n"
        f"ANCHOR RECEIPTS:\n{anchors}\n"
        f"TENSION / CONTEXT SOURCES:\n{context}\n"
        f"PLAUSIBLE EDITORIAL THESES:\n{theses}\n"
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
        "Write an 80-110 word Satoshi Shkreli / Biotica Media short-form monologue for skeptical, technically minded men 25-50. "
        "This is a perspective-driven investigation with receipts, not an abstract summary. Choose ONE defensible editorial thesis from the packet and organize the whole script around it. "
        "Open with the contradiction, suspicion, incentive, or uncomfortable question. Name the anchor paper, regulator, technology, or institution naturally. "
        "Use the MINIMUM evidence needed to make the thesis credible: normally one memorable numeric receipt, plus at most one additional finding if indispensable. "
        "Use a tension/context source when it genuinely deepens the story rather than merely adding another citation. Spend more words interpreting than listing data. "
        "State what is inference versus what is demonstrated. Give the strongest counter-case in one compact beat. End with a pointed verdict or unresolved question that makes the viewer want the next piece. "
        "Do not invent facts, give individualized medical advice, mention rhetorical mechanics, or imitate any real creator."
        + extra
    )


def generate_candidate(brief: dict, mechanics: list[dict] | None, key: str) -> str:
    return _response_text(
        model_for("writing"),
        "Write original Biotica Media copy in the Satoshi Shkreli voice. The value is a sharp, defensible perspective supported by selective receipts. Interpretation should outweigh recitation.",
        script_prompt(brief, mechanics),
        key,
        reasoning_for("writing"),
    )


def _perspective_judge(brief: dict, a: str, b: str, key: str) -> dict:
    props = {d: {"type": "number", "minimum": 1, "maximum": 5} for d in PERSPECTIVE_DIMENSIONS}
    score_obj = {"type": "object", "additionalProperties": False, "required": list(PERSPECTIVE_DIMENSIONS), "properties": props}
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["A", "B", "preferred", "publishable_A", "publishable_B"],
        "properties": {
            "A": score_obj,
            "B": score_obj,
            "preferred": {"type": "string", "enum": ["A", "B", "tie"]},
            "publishable_A": {"type": "boolean"},
            "publishable_B": {"type": "boolean"},
        },
    }
    body = {
        "model": model_for("editorial_reasoning"),
        "store": False,
        "reasoning": {"effort": reasoning_for("editorial_reasoning") or "high"},
        "instructions": (
            "Blindly judge which script works better as publishable Satoshi/Biotica short-form media. "
            "Do not reward abstract-like completeness or number density. Reward a clear perspective, selective evidence, interpretive insight, intellectual honesty, curiosity, and a compact counter-case. "
            "A script can be factually accurate and still score poorly if it feels like an abstract being read aloud."
        ),
        "input": f"RESEARCH PACKET:\n{evidence_text(brief)}\n\nCANDIDATE A:\n{a}\n\nCANDIDATE B:\n{b}",
        "max_output_tokens": 1400,
        "text": {"format": {"type": "json_schema", "name": "perspective_rhetoric_score", "strict": True, "schema": schema}},
    }
    result = _openai_json(RESPONSES_ENDPOINT, body, key)
    if result.get("status") != "completed":
        # One bounded retry gives the high-reasoning judge room to finish structured output.
        body["max_output_tokens"] = 2200
        result = _openai_json(RESPONSES_ENDPOINT, body, key)
    if result.get("status") != "completed":
        raise ValueError("Perspective judge response incomplete")
    raw = "".join(
        p.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for p in item.get("content", []) if p.get("type") == "output_text"
    )
    return json.loads(raw)


def run_real_benchmark(index: dict, top_k: int = 3) -> dict:
    key = _require_live()
    totals = {"none": {d: [] for d in PERSPECTIVE_DIMENSIONS}, "semantic": {d: [] for d in PERSPECTIVE_DIMENSIONS}}
    wins = {"none": 0, "semantic": 0, "tie": 0}
    publishable = {"none": 0, "semantic": 0}
    trials = []
    for brief in REAL_EVIDENCE_BRIEFS:
        query = brief["topic"] + " " + " ".join(brief["thesis_options"]) + " " + brief["counter_case"]
        selected = retrieve(index, query, top_k=top_k)
        baseline = generate_candidate(brief, None, key)
        semantic = generate_candidate(brief, selected, key)
        swap = int(hashlib.sha256(("perspective:" + brief["id"]).encode()).hexdigest(), 16) % 2 == 0
        a, b = (semantic, baseline) if swap else (baseline, semantic)
        labels = {"A": "semantic", "B": "none"} if swap else {"A": "none", "B": "semantic"}
        judged = _perspective_judge(brief, a, b, key)
        for blind in ("A", "B"):
            arm = labels[blind]
            for d in PERSPECTIVE_DIMENSIONS:
                totals[arm][d].append(float(judged[blind][d]))
            if judged[f"publishable_{blind}"]:
                publishable[arm] += 1
        pref = judged["preferred"]
        wins["tie" if pref == "tie" else labels[pref]] += 1
        trials.append({
            "brief_id": brief["id"],
            "topic": brief["topic"],
            "evidence": evidence_text(brief),
            "retrieved": [{k: m[k] for k in ("id", "episode_id", "mechanic_index", "function", "mechanic", "score")} for m in selected],
            "baseline_script": baseline,
            "semantic_script": semantic,
            "blind_order": labels,
            "judge": judged,
        })
    means = {arm: {d: sum(vals) / len(vals) for d, vals in dims.items()} for arm, dims in totals.items()}
    overall = {arm: sum(means[arm].values()) / len(PERSPECTIVE_DIMENSIONS) for arm in means}
    return {
        "schema_version": 3,
        "benchmark_target": "perspective_driven_investigation_with_receipts",
        "briefs_are_synthetic": False,
        "evidence_policy": "fixed_multi_source_research_packets",
        "arms": ["none", "semantic"],
        "dimensions": list(PERSPECTIVE_DIMENSIONS),
        "top_k": top_k,
        "means": means,
        "overall": overall,
        "semantic_delta": overall["semantic"] - overall["none"],
        "wins": wins,
        "publishable_counts": publishable,
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
        "publishable_counts": benchmark["publishable_counts"],
    }, indent=2))


if __name__ == "__main__":
    main()
