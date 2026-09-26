"""Deterministic brand identity treatment for Satoshi short-form video.

The hook owns the opening seconds. A subtle Biotica bug can be present immediately,
while the stronger host/channel identity beat lands in the body after retention is won.
"""
from __future__ import annotations

import hashlib

VARIANTS = ("dossier", "terminal", "receipt")


def _index(script_sha256: str) -> int:
    if not isinstance(script_sha256, str) or len(script_sha256.strip()) < 8:
        raise ValueError("A stable script hash is required for brand routing")
    digest = hashlib.sha256(script_sha256.strip().encode("utf-8")).digest()
    return digest[0] % len(VARIANTS)


def spec(script_sha256: str) -> dict:
    """Return a stable art-directed identity treatment for one script."""
    variant = VARIANTS[_index(script_sha256)]
    return {
        "schema_version": 1,
        "brand": "BIOTICA MEDIA",
        "host": "SATOSHI SHKRELI",
        "tagline": "MEN'S HEALTH // RECEIPTS REQUIRED",
        "variant": variant,
        # Preserve roughly the first 5.5 seconds for hook/value proposition.
        "start_frame": 165,
        # 1.6-second reveal: noticeable, but too short to feel like a bumper.
        "duration_frames": 48,
        # Tiny branding is allowed from frame zero; the full reveal is additive later.
        "bug_start_frame": 0,
        "bug_text": "BIOTICA MEDIA",
    }


def validate(value: dict) -> dict:
    required = {
        "schema_version", "brand", "host", "tagline", "variant",
        "start_frame", "duration_frames", "bug_start_frame", "bug_text",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Invalid brand intro fields")
    if value["variant"] not in VARIANTS:
        raise ValueError("Unknown brand intro variant")
    if value["brand"] != "BIOTICA MEDIA" or value["host"] != "SATOSHI SHKRELI":
        raise ValueError("Unexpected brand identity")
    if not 120 <= value["start_frame"] <= 210:
        raise ValueError("Full brand reveal should land after the opening hook")
    if not 30 <= value["duration_frames"] <= 60:
        raise ValueError("Brand reveal must stay brief")
    if not 0 <= value["bug_start_frame"] < value["start_frame"]:
        raise ValueError("Subtle brand bug must precede the full identity beat")
    return value
