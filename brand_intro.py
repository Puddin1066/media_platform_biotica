"""Deterministic brand identity treatment for Satoshi short-form video.

The brand beat overlays the host plate after the spoken hook has already begun.
It is intentionally brief: recognition without delaying the editorial payload.
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
        # Hook gets the first 0.6 seconds clean. Identity then lands for 1.4 sec.
        "start_frame": 18,
        "duration_frames": 42,
        # The tiny channel bug remains after the identity beat.
        "bug_start_frame": 60,
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
    if not 0 <= value["start_frame"] < 90:
        raise ValueError("Brand intro must land near the opening")
    if not 24 <= value["duration_frames"] <= 60:
        raise ValueError("Brand intro must stay brief")
    if value["bug_start_frame"] < value["start_frame"] + value["duration_frames"]:
        raise ValueError("Brand bug cannot precede identity beat completion")
    return value
