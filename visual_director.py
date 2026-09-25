"""Deterministic visual grammar for a 30-second Satoshi desk-satire short.

Ten rhetorical moves become ten semantic visual events, then compile into the
existing six five-second Remotion shot slots.
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

# Six renderer slots. Evidence and opening get two visual opportunities each
# because they carry the strongest attention/research burden.
SLOT_MOVES = [
    ("opening", "cold_open"),
    ("opening", "comic_turn"),
    ("explanations", "stakes"),
    ("evidence", "receipt"),
    ("limits", "reversal"),
    ("next_test", "callback"),
]

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
    for index, key in enumerate(SLOT_MOVES):
        event = by_key[key]
        prompt = prompt_for(event, script)
        slots.append({
            "slot": index,
            "cue_id": event["beat"],
            "move": event["move"],
            "visual_function": event["visual_function"],
            "prompt": prompt,
            "overlay_text": overlay_for(event),
            "source_urls": event["source_urls"],
        })
    return {
        "schema_version": 1,
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

def prompt_for(event, script):
    base = {
        "pattern_interrupt": "Immediate bold conceptual visual with one clear subject and strong motion;",
        "absurd_contrast": "Original satirical visual contrast that literalizes the joke without depicting a factual event;",
        "personal_consequence": "Clear male-health consequence visualization, legible on a phone;",
        "scale_or_intensify": "Escalating visual comparison or scale shift;",
        "evidence_receipt": "Document/data-inspired evidence visual; no fabricated paper screenshot, no fake chart values;",
        "annotation_or_punch_in": "Tight punch-in style visual emphasizing the key implication;",
        "contrast_reset": "Before/after or expectation-versus-evidence contrast;",
        "limitation_overlay": "Restrained uncertainty visual with a clear caveat motif;",
        "callback_visual": "Return to the opening visual motif so the ending visibly callbacks;",
        "reaction_or_end_card": "Simple host-compatible reaction/end visual with room for a final line;",
    }[event["visual_function"]]
    positioning = script.get("positioning", {})
    premise = positioning.get("positioned_premise", "")
    return (
        base + " vertical short inset, editorial illustration only, no real patient, "
        "no invented study result, no logos unless supplied and cleared. "
        "Spoken context: " + event["spoken_text"][:350] +
        ((" Positioned premise: " + premise[:250]) if premise else "")
    )

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
    if any(not s.get("prompt") or not s.get("visual_function") for s in slots):
        raise ValueError("Every renderer slot needs function and prompt")
    return value
