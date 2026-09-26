"""Deterministic narrative-mode routing for Satoshi content.

The router selects a rhetorical mechanics namespace, not a creator voice.
All modes share the same embedding space; mode only constrains retrieval.
"""
from __future__ import annotations

MODES = {"argumentative", "explanatory", "discovery"}

ARGUMENTATIVE_SIGNALS = {
    "myth", "scam", "fraud", "wrong", "controversy", "conflict", "debate",
    "lawsuit", "regulation", "ban", "banned", "industry", "marketing",
    "tradeoff", "trade-off", "versus", " vs ", "policy", "should",
}
DISCOVERY_SIGNALS = {
    "why", "mystery", "anomaly", "history", "origin", "strange", "unexpected",
    "hidden", "what happened", "how did", "where did", "surprising story",
}


def choose_mode(topic="", angle="", case=None, override=""):
    """Choose one retrieval namespace with an explicit override when supplied."""
    override = str(override or "").strip().lower()
    if override:
        if override not in MODES:
            raise ValueError("Unknown narrative mode")
        return override

    parts = [str(topic or ""), str(angle or "")]
    if isinstance(case, dict):
        parts.extend([str(case.get("question", "")), str(case.get("canon", ""))])
    text = " ".join(parts).lower()

    argumentative = sum(1 for signal in ARGUMENTATIVE_SIGNALS if signal in text)
    discovery = sum(1 for signal in DISCOVERY_SIGNALS if signal in text)
    if argumentative > discovery and argumentative:
        return "argumentative"
    if discovery > argumentative and discovery:
        return "discovery"
    return "explanatory"


def source_family_for_mode(mode):
    if mode not in MODES:
        raise ValueError("Unknown narrative mode")
    return {
        "argumentative": "lwt",
        "explanatory": "huberman",
        "discovery": "revisionist",
    }[mode]
