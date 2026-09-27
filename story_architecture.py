"""Evidence-driven story architecture for Biotica Media.

This layer defines the causal story the research/writing agent must resolve before
compressing material into format-specific production beats. It does not supply
facts, imitate a creator, or replace source review.
"""
from __future__ import annotations

import os

STAGES = (
    "prevailing_belief",
    "belief_origin",
    "destabilizing_receipt",
    "central_anomaly",
    "competing_explanations",
    "satoshi_synthesis",
)

_STAGE_SPECS = {
    "prevailing_belief": {
        "job": "State what the relevant audience, clinicians, regulators, or market currently tends to believe.",
        "research_question": "What is the baseline belief or advice, and how confidently is it actually held?",
        "evidence_priority": ["guideline", "regulatory_label", "consensus_statement", "large_review", "market_behavior"],
    },
    "belief_origin": {
        "job": "Explain why that belief formed rather than merely repeating it.",
        "research_question": "Which historical study, regulatory action, commercial pattern, mechanism, or cultural event made this belief plausible?",
        "evidence_priority": ["original_study", "regulatory_history", "historical_review", "prescribing_or_market_data"],
    },
    "destabilizing_receipt": {
        "job": "Introduce one concrete, sourceable result that materially weakens or complicates the baseline belief.",
        "research_question": "What is the strongest specific paper, trial, dataset, patent, filing, label change, or other primary receipt?",
        "evidence_priority": ["randomized_trial", "primary_dataset", "regulatory_action", "patent_or_filing", "primary_literature"],
    },
    "central_anomaly": {
        "job": "Name the contradiction, incentive mismatch, omission, unexplained pattern, or second-order effect created by the receipt.",
        "research_question": "What remains genuinely strange after the strongest evidence is accounted for?",
        "evidence_priority": ["cross_source_conflict", "secondary_endpoint", "implementation_gap", "market_or_policy_mismatch"],
    },
    "competing_explanations": {
        "job": "Present at least two plausible explanations that could account for the anomaly without forcing a preferred conclusion.",
        "research_question": "What are the strongest competing interpretations, and what evidence would discriminate between them?",
        "evidence_priority": ["mechanistic_evidence", "contrary_study", "expert_or_guideline_interpretation", "bias_or_incentive_analysis"],
    },
    "satoshi_synthesis": {
        "job": "State the best-supported synthesis, residual uncertainty, and why the audience should care now.",
        "research_question": "What can be concluded, what cannot, and what practical or commercial consequence follows?",
        "evidence_priority": ["weight_of_evidence", "decision_relevance", "remaining_uncertainty"],
    },
}


def enabled():
    """Allow clean A/B comparison with the legacy prompt architecture."""
    return os.environ.get("SATOSHI_STORY_ARCHITECTURE_ENABLED", "true").lower() != "false"


def build(case, format_name="short"):
    """Return a factual-neutral architecture contract for a researched case."""
    if not isinstance(case, dict):
        raise ValueError("Case must be an object")
    question = str(case.get("question", "")).strip()
    if not question:
        raise ValueError("Case question required")
    hypotheses = case.get("hypotheses", [])
    if not isinstance(hypotheses, list) or not hypotheses:
        raise ValueError("Case hypotheses required")

    compression = (
        "For short-form, preserve the causal order but compress adjacent stages; not every stage needs its own sentence. "
        "The destabilizing receipt and competing explanations must remain identifiable."
        if format_name == "short"
        else "Give each stage enough space to make the causal transition explicit; background is included only when it explains the next turn."
    )
    return {
        "version": "six-stage-v1",
        "question": question,
        "sequence": list(STAGES),
        "stages": [
            {"name": name, **_STAGE_SPECS[name]}
            for name in STAGES
        ],
        "rules": [
            "Research first; do not populate a stage from the rhetoric corpus.",
            "Background must explain why a belief or institution behaved as it did; omit decorative chronology.",
            "Use at least two plausible competing explanations when evidence permits.",
            "Separate observed evidence from inference, motive, and speculation.",
            "Synthesis must state residual uncertainty rather than manufacture resolution.",
            compression,
        ],
    }


def beat_mapping():
    """Compatibility map from story logic into the existing five production beats."""
    return {
        "opening": ["prevailing_belief", "destabilizing_receipt"],
        "explanations": ["belief_origin", "competing_explanations"],
        "evidence": ["destabilizing_receipt"],
        "limits": ["central_anomaly", "competing_explanations"],
        "next_test": ["satoshi_synthesis"],
    }
