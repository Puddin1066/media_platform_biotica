"""Build an overcomplete visual candidate library from Satoshi visual direction.

This module is deliberately provider-agnostic. It converts each semantic visual
slot into several candidate asset briefs so downstream directors can choose
between evidence, native Remotion graphics, illustrative stills and selective
motion without regenerating the episode.

The expensive unit is the asset candidate, not the final edit.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class Candidate:
    asset_id: str
    slot_key: str
    cue_id: str
    candidate_type: str
    purpose: str
    prompt: str | None
    source_urls: tuple[str, ...]
    factual_status: str
    preferred_seconds: float
    estimated_runway_credits: int
    remotion_treatment: str
    selection_tags: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        row = asdict(self)
        row["source_urls"] = list(self.source_urls)
        row["selection_tags"] = list(self.selection_tags)
        return row


def _native_candidate(slot: dict[str, Any]) -> Candidate:
    fn = slot["visual_function"]
    treatment = {
        "evidence_receipt": "source-card or native chart with citation label and animated highlight",
        "annotation_or_punch_in": "native punch-in, crop, arrow and short source label",
        "limitation_overlay": "large LIMIT typography with source-supported qualifier",
        "absurd_contrast": "two-panel native contrast card with one concise punchline",
    }.get(fn, "native typography/callout synchronized to the spoken phrase")
    return Candidate(
        asset_id=f'{slot["cue_id"]}-{slot["move"]}-native',
        slot_key=f'{slot["cue_id"]}:{slot["move"]}',
        cue_id=slot["cue_id"],
        candidate_type="remotion_native",
        purpose="zero-credit explanatory fallback",
        prompt=None,
        source_urls=tuple(slot.get("source_urls") or []),
        factual_status="source_bound" if slot.get("source_urls") else "commentary",
        preferred_seconds=2.5,
        estimated_runway_credits=0,
        remotion_treatment=treatment,
        selection_tags=("clarity", "credibility", "cheap"),
    )


def _evidence_candidate(slot: dict[str, Any]) -> Candidate:
    urls = tuple(slot.get("source_urls") or [])
    return Candidate(
        asset_id=f'{slot["cue_id"]}-{slot["move"]}-evidence',
        slot_key=f'{slot["cue_id"]}:{slot["move"]}',
        cue_id=slot["cue_id"],
        candidate_type="evidence",
        purpose="show the receipt when the beat makes a factual claim",
        prompt=None,
        source_urls=urls,
        factual_status="requires_source_asset" if urls else "not_available",
        preferred_seconds=3.5,
        estimated_runway_credits=0,
        remotion_treatment="crop/zoom real source material; overlay citation and highlight only verified regions",
        selection_tags=("credibility", "clarity", "receipt"),
    )


def _still_candidate(slot: dict[str, Any], index: int) -> Candidate:
    spec = slot["shot_spec"]
    variation = (
        "Make the concept immediately legible in a phone-sized frame. "
        "Use one dominant subject and preserve negative space for native captions."
        if index == 1
        else
        "Create a sharper editorial alternative with a different composition and visual metaphor. "
        "Avoid text, numbers, logos and fabricated evidence."
    )
    return Candidate(
        asset_id=f'{slot["cue_id"]}-{slot["move"]}-still-{index}',
        slot_key=f'{slot["cue_id"]}:{slot["move"]}',
        cue_id=slot["cue_id"],
        candidate_type="generated_still",
        purpose="editorial illustration with multiple compositional choices",
        prompt=(slot["prompt"] + " " + variation)[:2200],
        source_urls=tuple(slot.get("source_urls") or []),
        factual_status="illustration",
        preferred_seconds=3.0,
        estimated_runway_credits=2,
        remotion_treatment="slow crop/zoom, parallax or hold; native source/caption layers remain separate",
        selection_tags=("comedy", "retention", "illustration"),
    )


def _motion_candidate(slot: dict[str, Any]) -> Candidate:
    spec = slot["shot_spec"]
    motion_prompt = (
        f'{spec["subject"]}. {spec["subject_motion"]}. '
        f'{spec["camera"]}. Keep the action singular and readable within four seconds. '
        "No visible speaking, readable text, charts, logos or fabricated documents."
    )
    return Candidate(
        asset_id=f'{slot["cue_id"]}-{slot["move"]}-motion',
        slot_key=f'{slot["cue_id"]}:{slot["move"]}',
        cue_id=slot["cue_id"],
        candidate_type="generated_motion",
        purpose="selective motion for pattern interruption, escalation, joke or callback",
        prompt=motion_prompt[:1200],
        source_urls=tuple(slot.get("source_urls") or []),
        factual_status="illustration",
        preferred_seconds=4.0,
        estimated_runway_credits=20,
        remotion_treatment="full-frame or dominant cutaway; enter on phrase boundary and exit before next factual claim",
        selection_tags=("retention", "comedy", "motion"),
    )


MOTION_FUNCTIONS = {
    "pattern_interrupt",
    "absurd_contrast",
    "scale_or_intensify",
    "callback_visual",
    "reaction_or_end_card",
}


def compile_library(direction: dict[str, Any], *, max_motion: int = 4,
                    stills_per_slot: int = 2) -> dict[str, Any]:
    """Compile several candidate assets for each render slot.

    The library intentionally overproduces cheap options while rationing motion.
    No provider calls occur here.
    """
    import visual_director

    visual_director.validate(direction)
    if not 1 <= stills_per_slot <= 4:
        raise ValueError("stills_per_slot must be 1-4")
    if not 0 <= max_motion <= 6:
        raise ValueError("max_motion must be 0-6")

    candidates: list[Candidate] = []
    motion_used = 0
    by_slot: dict[str, list[str]] = {}

    for slot in direction["render_slots"]:
        slot_key = f'{slot["cue_id"]}:{slot["move"]}'
        local: list[Candidate] = [_native_candidate(slot)]
        if slot.get("source_urls"):
            local.append(_evidence_candidate(slot))
        for index in range(1, stills_per_slot + 1):
            local.append(_still_candidate(slot, index))
        if slot["visual_function"] in MOTION_FUNCTIONS and motion_used < max_motion:
            local.append(_motion_candidate(slot))
            motion_used += 1

        for candidate in local:
            candidates.append(candidate)
        by_slot[slot_key] = [candidate.asset_id for candidate in local]

    runway_estimate = sum(c.estimated_runway_credits for c in candidates)
    return {
        "schema_version": 1,
        "status": "candidate_library_ready",
        "strategy": "overcomplete_coverage_then_select",
        "candidate_count": len(candidates),
        "estimated_runway_credits_if_all_generated": runway_estimate,
        "generation_policy": {
            "cheap_first": True,
            "generate_all_stills": True,
            "motion_is_optional": True,
            "motion_retry_requires_critic_request": True,
            "evidence_assets_are_never_synthesized": True,
        },
        "by_slot": by_slot,
        "candidates": [c.json() for c in candidates],
    }


def validate_library(value: dict[str, Any]) -> dict[str, Any]:
    if value.get("status") != "candidate_library_ready":
        raise ValueError("candidate library required")
    rows = value.get("candidates")
    if not isinstance(rows, list) or not rows:
        raise ValueError("candidate library cannot be empty")
    ids = [row.get("asset_id") for row in rows]
    if None in ids or len(ids) != len(set(ids)):
        raise ValueError("candidate asset IDs must be unique")
    required = {
        "asset_id", "slot_key", "cue_id", "candidate_type", "purpose", "source_urls",
        "factual_status", "preferred_seconds", "estimated_runway_credits",
        "remotion_treatment", "selection_tags",
    }
    for row in rows:
        if not required.issubset(row):
            raise ValueError("candidate record is incomplete")
        if row["candidate_type"] == "evidence" and not row["source_urls"]:
            raise ValueError("evidence candidate requires source URLs")
    return value
