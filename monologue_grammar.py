"""Deterministic rhetorical grammar for the Satoshi desk-satire short.

This defines repeatable *functions*, not another show's wording, jokes, voice, or
performance. The model supplies original lines; the validator enforces order,
callback continuity, and exact compilation into the existing five-beat script.
"""
import re

BEAT_MOVES = {
    "opening": ("cold_open", "comic_turn"),
    "explanations": ("stakes", "escalation"),
    "evidence": ("receipt", "reveal"),
    "limits": ("reversal", "qualification"),
    "next_test": ("callback", "button"),
}

MOVE_PURPOSE = {
    "cold_open": "State the consequential anomaly/premise immediately.",
    "comic_turn": "Add an original absurd contrast, analogy, or reaction without adding unsupported facts.",
    "stakes": "Explain why the audience should care personally or intellectually.",
    "escalation": "Broaden or intensify the situation with a second comic or conceptual turn.",
    "receipt": "Present the strongest concrete source-backed number, finding, document, or observation.",
    "reveal": "Explain what the receipt changes about the initial framing.",
    "reversal": "Undercut the tempting overclaim or simplistic conclusion.",
    "qualification": "State the most important uncertainty or limitation naturally.",
    "callback": "Return explicitly to the opening anchor/image/phrase.",
    "button": "End on a sharp unresolved question, test, or original comic button; no generic CTA.",
}

GENERIC_CTA = ("follow for more", "like and subscribe", "subscribe for more")
BANNED_OPENERS = ("hi ", "hello ", "hey ", "welcome ", "today ", "did you know")

def _words(text):
    return re.findall(r"\b[\w’'-]+\b", text or "")

def expected_moves(beat):
    if beat not in BEAT_MOVES:
        raise ValueError("Unknown beat")
    return list(BEAT_MOVES[beat])

def compile_segment(segment):
    beat = segment.get("beat")
    moves = segment.get("monologue_moves")
    if not isinstance(moves, list) or [m.get("function") for m in moves] != expected_moves(beat):
        raise ValueError("Monologue moves do not match deterministic beat grammar")
    lines = []
    for move in moves:
        if set(move) != {"function", "text"} or not isinstance(move["text"], str) or not move["text"].strip():
            raise ValueError("Every monologue move needs exactly function + nonempty text")
        lines.append(move["text"].strip())
    return " ".join(lines)

def validate_script(script):
    segments = script.get("segments") if isinstance(script, dict) else None
    if not isinstance(segments, list) or [s.get("beat") for s in segments] != list(BEAT_MOVES):
        raise ValueError("Expected the five canonical beats in order")
    anchor = str(script.get("callback_anchor", "")).strip()
    if not anchor or len(_words(anchor)) > 5:
        raise ValueError("callback_anchor must be a concrete phrase of 1–5 words")

    for segment in segments:
        compiled = compile_segment(segment)
        if segment.get("text", "").strip() != compiled:
            raise ValueError("Segment text must exactly equal its compiled monologue moves")

    opening = segments[0]["monologue_moves"][0]["text"].strip()
    if opening.lower().startswith(BANNED_OPENERS):
        raise ValueError("Cold open must start with substance")
    if not 1 <= len(_words(opening)) <= 12:
        raise ValueError("Cold open must contain 1–12 words")

    opening_block = (segments[0]["text"] + " " + anchor).lower()
    callback = segments[-1]["monologue_moves"][0]["text"].lower()
    if anchor.lower() not in opening_block or anchor.lower() not in callback:
        raise ValueError("Callback must explicitly reuse callback_anchor")

    total = sum(len(_words(s["text"])) for s in segments)
    if not 55 <= total <= 95:
        raise ValueError("Short must contain 55–95 spoken words")

    ending = segments[-1]["text"].lower()
    if any(x in ending for x in GENERIC_CTA):
        raise ValueError("Generic engagement CTA is not allowed")

    return {
        "status": "pass",
        "spoken_words": total,
        "callback_anchor": anchor,
        "move_sequence": [m for beat in BEAT_MOVES.values() for m in beat],
        "publishable": False,
        "note": "Rhetorical-structure validation only; factual review remains separate.",
    }
