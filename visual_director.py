"""Deterministic visual grammar and prompt compiler for Satoshi shorts.

Ten rhetorical moves become ten semantic visual events, then compile into six
five-second Runway shot specifications. Rich direction stays structured; only
compact, non-conflicting instructions are sent to the provider.
"""
from monologue_grammar import BEAT_MOVES

VISUAL_FUNCTIONS = {
    "cold_open": "pattern_interrupt",
    "comic_turn": "absurd_contrast",
    "stakes": "personal_consequence",
    "escalation": "scale_or_intensify",
    "receipt": "evidence_receipt",
    "reveal": "annotation_or_punch_in",
    "reversal": "contrast_reset",
    "qualification": "limitation_overlay",
    "callback": "callback_visual",
    "button": "reaction_or_end_card",
}

SLOT_MOVES = [
    ("opening", "cold_open"),
    ("opening", "comic_turn"),
    ("explanations", "stakes"),
    ("evidence", "receipt"),
    ("limits", "reversal"),
    ("next_test", "callback"),
]

# Deliberately different visual grammars keep the reel from looking like six
# variants of generic cinematic health B-roll.
SHOT_GRAMMARS = {
    "pattern_interrupt": {
        "composition": "extreme close-up or bold single-subject composition",
        "camera": "fast push-in followed by a brief locked hold",
        "subject_motion": "one immediately legible physical action",
        "environment_motion": "subtle secondary motion only",
        "lighting": "high-contrast clinical or institutional light",
        "aesthetic": "photoreal editorial documentary with a slightly uncanny edge",
        "energy": "high",
        "literalness": "conceptual metaphor grounded in plausible objects",
        "overlay_safe_area": "leave upper-right negative space",
        "timing": "0-1.5s establish contradiction; 1.5-3.5s reveal; 3.5-5s hold the visual question",
    },
    "absurd_contrast": {
        "composition": "medium shot with two visually opposed elements in one frame",
        "camera": "small lateral track or rack-focus reveal",
        "subject_motion": "one dry comic visual action, physically plausible",
        "environment_motion": "restrained ambient movement",
        "lighting": "naturalistic commercial-documentary light",
        "aesthetic": "deadpan photoreal satire, not cartoonish",
        "energy": "medium-high",
        "literalness": "comic metaphor, never a fabricated factual event",
        "overlay_safe_area": "leave left-third negative space",
        "timing": "0-2s establish normal scene; 2-4s reveal contradiction; 4-5s reaction hold",
    },
    "personal_consequence": {
        "composition": "human-scale environmental close or medium shot without identifiable patient",
        "camera": "steady slow dolly toward the consequence",
        "subject_motion": "clear cause-to-effect physical progression",
        "environment_motion": "realistic ambient movement",
        "lighting": "credible real-world clinical or domestic light",
        "aesthetic": "grounded documentary realism",
        "energy": "medium",
        "literalness": "literal mechanism or consequence without implying an observed patient event",
        "overlay_safe_area": "keep one clean vertical third for labels",
        "timing": "0-2s establish context; 2-4s show consequence; 4-5s settle for annotation",
    },
    "evidence_receipt": {
        "composition": "overhead or desk-level evidence tableau with one dominant document or data object",
        "camera": "controlled push-in or precise punch-in",
        "subject_motion": "a hand, marker, cursor-like light, or paper movement isolates the key evidence area",
        "environment_motion": "minimal movement so evidence remains legible",
        "lighting": "neutral hospital, lab, records-room, or newsroom light",
        "aesthetic": "investigative documentary evidence shot",
        "energy": "restrained",
        "literalness": "data-inspired illustration only; never fabricate exact paper text, logos, or numeric results",
        "overlay_safe_area": "leave one side clean for sourced Remotion annotation",
        "timing": "0-2s establish evidence object; 2-4s isolate key region; 4-5s hold for receipt overlay",
    },
    "contrast_reset": {
        "composition": "single frame containing a before-versus-after or belief-versus-evidence contrast",
        "camera": "slow reveal, split-depth rack focus, or controlled orbit",
        "subject_motion": "one element replaces, covers, or visually contradicts another",
        "environment_motion": "subtle continuity motion",
        "lighting": "shift from confident/high-key to ambiguous/neutral light",
        "aesthetic": "institutional thriller documentary realism",
        "energy": "medium",
        "literalness": "conceptual contrast, not a claim of historical footage",
        "overlay_safe_area": "leave center-top or upper-right clear",
        "timing": "0-2s show prevailing belief; 2-4s introduce contradicting evidence; 4-5s unresolved hold",
    },
    "callback_visual": {
        "composition": "recognizable transformed echo of the opening composition",
        "camera": "reverse or gentler version of the opening camera move",
        "subject_motion": "opening object returns with one changed detail that embodies uncertainty or the next test",
        "environment_motion": "quiet ambient movement",
        "lighting": "same family as opening but calmer and more resolved",
        "aesthetic": "photoreal editorial callback with visual continuity",
        "energy": "low-medium",
        "literalness": "conceptual callback",
        "overlay_safe_area": "leave lower or upper third clean for final line",
        "timing": "0-2s recognition; 2-4s changed detail; 4-5s final unresolved hold",
    },
}


def _segments(script):
    segments = script.get("segments") if isinstance(script, dict) else None
    if not isinstance(segments, list) or [s.get("beat") for s in segments] != list(BEAT_MOVES):
        raise ValueError("Five canonical script beats required for visual direction")
    return segments


def plan(script):
    segments = _segments(script)
    events = []
    for segment in segments:
        for move in segment.get("monologue_moves", []):
            fn = move.get("function")
            if fn not in VISUAL_FUNCTIONS:
                raise ValueError("Unknown monologue move for visual direction")
            events.append({
                "beat": segment["beat"],
                "move": fn,
                "visual_function": VISUAL_FUNCTIONS[fn],
                "spoken_text": move["text"],
                "production_note": segment.get("production_note", ""),
                "source_urls": segment.get("source_urls", []),
            })
    if len(events) != 10:
        raise ValueError("Exactly ten rhetorical visual events required")

    by_key = {(e["beat"], e["move"]): e for e in events}
    slots = []
    opening_spec = None
    for index, key in enumerate(SLOT_MOVES):
        event = by_key[key]
        spec = shot_spec_for(event, script, opening_spec=opening_spec)
        if index == 0:
            opening_spec = spec
        prompt = compile_prompt(spec)
        slots.append({
            "slot": index,
            "cue_id": event["beat"],
            "move": event["move"],
            "visual_function": event["visual_function"],
            "shot_spec": spec,
            "prompt": prompt,
            "overlay_text": overlay_for(event),
            "source_urls": event["source_urls"],
        })
    return {
        "schema_version": 2,
        "events": events,
        "render_slots": slots,
        "status": "visual_direction_ready",
        "publishable": False,
    }


def overlay_for(event):
    text = event["spoken_text"].strip()
    words = text.split()
    if event["visual_function"] == "evidence_receipt":
        return "SOURCE RECEIPT"
    if event["visual_function"] == "limitation_overlay":
        return "LIMIT"
    return " ".join(words[:6]).upper()


def _subject_for(event, script):
    note = event.get("production_note", "").strip()
    positioning = script.get("positioning", {})
    premise = positioning.get("positioned_premise", "").strip()
    spoken = event["spoken_text"].strip()
    context = note or premise or spoken
    return context[:280]


def shot_spec_for(event, script, opening_spec=None):
    fn = event["visual_function"]
    grammar_key = fn if fn in SHOT_GRAMMARS else {
        "scale_or_intensify": "personal_consequence",
        "annotation_or_punch_in": "evidence_receipt",
        "limitation_overlay": "contrast_reset",
        "reaction_or_end_card": "callback_visual",
    }[fn]
    grammar = dict(SHOT_GRAMMARS[grammar_key])
    positioning = script.get("positioning", {})
    premise = positioning.get("positioned_premise", "").strip()
    subject = _subject_for(event, script)

    if fn == "evidence_receipt":
        subject = "a realistic clinical-trial or regulatory evidence object representing: " + subject
    elif fn == "callback_visual" and opening_spec:
        subject = "a transformed callback to the opening motif, now reflecting: " + subject
    elif fn == "contrast_reset":
        subject = "a visual contradiction between the prevailing belief and the newer evidence: " + subject

    spec = {
        "subject": subject,
        "environment": "credible contemporary clinical, institutional, laboratory, records-room, or domestic setting as appropriate",
        "composition": grammar["composition"],
        "camera": grammar["camera"],
        "subject_motion": grammar["subject_motion"],
        "environment_motion": grammar["environment_motion"],
        "timing": grammar["timing"],
        "lighting": grammar["lighting"],
        "aesthetic": grammar["aesthetic"],
        "editorial_function": fn,
        "energy": grammar["energy"],
        "continuity": "same restrained clinical-documentary world, tactile materials, realistic optics, no glossy generic AI look",
        "overlay_safe_area": grammar["overlay_safe_area"],
        "literalness": grammar["literalness"],
        "safety": "no identifiable real patient, no fabricated exact study text or numeric values, no uncleared logos, no embedded captions or watermarks",
        "spoken_context": event["spoken_text"][:320],
        "positioned_premise": premise[:240],
    }
    if fn == "callback_visual" and opening_spec:
        spec["continuity_reference"] = {
            "composition": opening_spec["composition"],
            "lighting": opening_spec["lighting"],
            "aesthetic": opening_spec["aesthetic"],
        }
    return spec


def compile_prompt(spec):
    """Compile a rich shot spec into a compact Runway instruction.

    Richness is retained in the JSON plan; the provider prompt stays direct,
    concrete, and non-conflicting.
    """
    parts = [
        spec["aesthetic"].capitalize() + ".",
        "Subject: " + spec["subject"] + ".",
        "Setting: " + spec["environment"] + ".",
        "Composition: " + spec["composition"] + ".",
        "Camera: " + spec["camera"] + ".",
        "Action: " + spec["subject_motion"] + ".",
        "Environment motion: " + spec["environment_motion"] + ".",
        "Timing over 5 seconds: " + spec["timing"] + ".",
        "Lighting: " + spec["lighting"] + ".",
        "Continuity: " + spec["continuity"] + ".",
        "Framing: " + spec["overlay_safe_area"] + ".",
        "Constraint: " + spec["literalness"] + ". " + spec["safety"] + ".",
    ]
    prompt = " ".join(parts)
    return prompt[:1800]


def prompt_for(event, script):
    # Backward-compatible helper used by older callers/tests.
    return compile_prompt(shot_spec_for(event, script))


def validate(value):
    if not isinstance(value, dict) or value.get("status") != "visual_direction_ready":
        raise ValueError("Visual direction plan required")
    events, slots = value.get("events"), value.get("render_slots")
    if not isinstance(events, list) or len(events) != 10:
        raise ValueError("Visual direction needs ten semantic events")
    if not isinstance(slots, list) or len(slots) != 6:
        raise ValueError("Visual direction must compile to six renderer slots")
    if [s.get("slot") for s in slots] != list(range(6)):
        raise ValueError("Renderer slots must be ordered 0–5")
    required = {
        "subject", "environment", "composition", "camera", "subject_motion",
        "environment_motion", "timing", "lighting", "aesthetic",
        "editorial_function", "energy", "continuity", "overlay_safe_area",
        "literalness", "safety",
    }
    for slot in slots:
        if not slot.get("prompt") or not slot.get("visual_function"):
            raise ValueError("Every renderer slot needs function and prompt")
        spec = slot.get("shot_spec")
        if not isinstance(spec, dict) or not required.issubset(spec):
            raise ValueError("Every renderer slot needs a complete structured shot spec")
        if len(slot["prompt"]) > 1800:
            raise ValueError("Compiled Runway prompt must remain bounded")
    if len({s["shot_spec"]["aesthetic"] for s in slots}) < 4:
        raise ValueError("Six-shot plan must use differentiated visual grammars")
    return value
