"""Structural validator for 30-second Satoshi short drafts."""
import re
from produce import BEATS
import monologue_grammar

BANNED_OPENERS = ("hi ", "hello ", "hey ", "today ", "welcome ", "did you know")
GENERIC_ENDINGS = ("follow for more", "like and subscribe", "subscribe for more")

def words(text):
    return re.findall(r"\b[\w’'-]+\b", text or "")

def validate_script(script):
    monologue_grammar.validate_script(script)
    segments = script.get("segments") if isinstance(script, dict) else None
    if not isinstance(segments, list) or [s.get("beat") for s in segments] != BEATS:
        raise ValueError("Satoshi short needs the existing five ordered beats")
    opening = segments[0].get("text", "").strip()
    first_sentence = re.split(r"(?<=[.!?])\s+", opening)[0]
    first_words = words(first_sentence)
    if not first_words or len(first_words) > 12:
        raise ValueError("Opening first sentence must contain 1–12 words")
    if opening.lower().startswith(BANNED_OPENERS):
        raise ValueError("Opening must begin with substance, not an introduction")
    total = sum(len(words(s.get("text", ""))) for s in segments)
    if total > 95:
        raise ValueError("Short exceeds 95 spoken words")
    if total < 45:
        raise ValueError("Short is too thin for the 30-second format")
    for segment in segments:
        if not segment.get("source_urls"):
            raise ValueError("Every beat needs at least one cited source URL")
        if not str(segment.get("production_note", "")).strip():
            raise ValueError("Every beat needs a visual production note")
    ending = segments[-1].get("text", "").strip().lower()
    if any(x in ending for x in GENERIC_ENDINGS):
        raise ValueError("Use an open question/callback, not a generic CTA")
    return {
        "status": "pass",
        "spoken_words": total,
        "opening_first_sentence_words": len(first_words),
        "beats": list(BEATS),
        "publishable": False,
        "note": "Structural validation only; scientific review is still required."
    }
