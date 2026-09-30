"""Sentence-level performance direction for canonical Satoshi narration.

This module does not rewrite editorial copy. It assigns an acting intention to
individual spoken sentences so the speech model gets explicit changes in pace,
energy, emphasis, and pause behavior inside a story beat.
"""
from __future__ import annotations

import re

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'“‘])")

ROLE_DIRECTIONS = {
    "hook": "quick, confident, intrigued; land the surprising premise immediately; no announcer energy",
    "intrigue": "slightly quieter and more curious; make the listener lean in; allow a small pause after the reveal",
    "mechanism": "clear and conversational; explain rather than lecture; moderate pace with crisp causal emphasis",
    "receipt": "slower and flatter emotionally; factual, authoritative, and precise; let important evidence breathe",
    "correction": "firm and skeptical; slow slightly on the negation; sound like you are preventing a bad inference",
    "objection": "measured, doubtful, intellectually fair; lower energy rather than becoming dramatic",
    "dry_humor": "underplay the joke; slight amusement, almost tossed away; never punch the line like a comedian",
    "synthesis": "deliberate and confident; broaden from the fact to the insight; slightly slower than the setup",
    "payoff": "relaxed confidence; brief pause before the line; make it feel inevitable rather than theatrical",
}

_HUMOR_MARKERS = (
    "dragons", "steam", "angry stranger", "family lineage", "four hundred times",
    "for a hat", "middle management", "lose our minds",
)
_CORRECTION_MARKERS = (
    "does not", "doesn't", "do not", "don't", "not the same", "not treatment",
    "not efficacy", "we do not know", "would be nonsense", "that is too strong",
)
_EVIDENCE_MARKERS = (
    "study", "studies", "trial", "randomized", "researchers", "evidence", "found",
    "reported", "authorized", "fda", "patients", "participants", "meta-analysis",
)


def split_sentences(text: str) -> list[str]:
    text = " ".join(str(text or "").split()).strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENTENCE_RE.split(text) if p.strip()]
    return parts or [text]


def classify_sentence(beat: str, sentence: str, index: int, total: int) -> str:
    lower = sentence.lower()
    if any(marker in lower for marker in _HUMOR_MARKERS):
        return "dry_humor"
    if any(marker in lower for marker in _CORRECTION_MARKERS):
        return "correction"
    if beat == "opening":
        return "hook" if index == 0 else "intrigue"
    if beat == "evidence" or any(marker in lower for marker in _EVIDENCE_MARKERS):
        return "receipt"
    if beat == "limits":
        return "objection"
    if beat == "explanations":
        return "mechanism"
    if beat == "next_test":
        return "payoff" if index == total - 1 else "synthesis"
    if sentence.endswith("?"):
        return "intrigue"
    return "mechanism"


def performance_score(beat: str, text: str) -> list[dict]:
    sentences = split_sentences(text)
    score = []
    for index, sentence in enumerate(sentences):
        role = classify_sentence(beat, sentence, index, len(sentences))
        score.append({
            "sentence_index": index + 1,
            "text": sentence,
            "role": role,
            "direction": ROLE_DIRECTIONS[role],
        })
    return score


def performance_instructions(base_instructions: str, beat: str, text: str) -> tuple[str, list[dict]]:
    score = performance_score(beat, text)
    directions = [
        base_instructions.strip(),
        "Treat this as an acted editorial performance, not a uniform read. Change prosody between sentences while preserving the words exactly.",
    ]
    for item in score:
        prefix = item["text"][:54].replace("\n", " ")
        directions.append(
            f"Sentence {item['sentence_index']} (starts: {prefix!r}): {item['direction']}."
        )
    directions.append(
        "Use natural micro-pauses at thought boundaries. Avoid constant pitch, constant speed, exaggerated emotion, sing-song cadence, and artificial emphasis on every sentence."
    )
    return " ".join(directions), score
