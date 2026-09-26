"""Deterministic Biotica Media identity treatment for Satoshi short-form video.

The durable brand grammar is fixed. Episode-specific text changes with the story,
so recognition compounds without requiring a newly generated bumper each render.
"""
from __future__ import annotations

import hashlib
import re

VARIANTS = ("dossier", "terminal", "receipt")


def _index(script_sha256: str) -> int:
    if not isinstance(script_sha256, str) or len(script_sha256.strip()) < 8:
        raise ValueError("A stable script hash is required for brand routing")
    value = hashlib.sha256(script_sha256.strip().encode("utf-8")).digest()
    return value[0] % len(VARIANTS)


def _episode_label(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip().upper()
    return text[:52] if text else "MEN'S HEALTH INTELLIGENCE"


def spec(script_sha256: str, episode_label: str = "") -> dict:
    """Return fixed brand grammar plus deterministic episode-specific context."""
    clean_sha = script_sha256.strip().lower()
    return {
        "schema_version": 2,
        "brand": "BIOTICA MEDIA",
        "host": "SATOSHI SHKRELI",
        "tagline": "MEN'S HEALTH // RECEIPTS REQUIRED",
        "variant": VARIANTS[_index(clean_sha)],
        "case_id": clean_sha[:6].upper(),
        "episode_label": _episode_label(episode_label),
        # Full identity reveal follows the hook rather than competing with it.
        "start_frame": 165,
        "duration_frames": 48,
        # Tiny brand bug is the only opening branding.
        "bug_start_frame": 0,
        "bug_text": "BIOTICA MEDIA",
    }


def validate(value: dict) -> dict:
    required = {
        "schema_version", "brand", "host", "tagline", "variant", "case_id",
        "episode_label", "start_frame", "duration_frames", "bug_start_frame", "bug_text",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Invalid brand identity fields")
    if value["schema_version"] != 2 or value["variant"] not in VARIANTS:
        raise ValueError("Unknown brand identity version or variant")
    if value["brand"] != "BIOTICA MEDIA" or value["host"] != "SATOSHI SHKRELI":
        raise ValueError("Unexpected brand identity")
    if not re.fullmatch(r"[0-9A-F]{6}", value["case_id"]):
        raise ValueError("case_id must be a stable six-character hex identifier")
    if not isinstance(value["episode_label"], str) or not 1 <= len(value["episode_label"]) <= 52:
        raise ValueError("episode_label must contain 1–52 characters")
    if not 120 <= value["start_frame"] <= 210:
        raise ValueError("Full brand reveal should land after the opening hook")
    if not 30 <= value["duration_frames"] <= 60:
        raise ValueError("Brand reveal must stay brief")
    if not 0 <= value["bug_start_frame"] < value["start_frame"]:
        raise ValueError("Subtle brand bug must precede the full identity beat")
    return value
