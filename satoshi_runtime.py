"""Canonical Satoshi runtime selector.

There is one production engine: satoshi_supervisor.py.  This wrapper exposes only
two supported operating profiles so preview and production cannot drift into
separate creative pipelines.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

PROFILES = {
    "preview": {
        "publish": False,
        "visual_mode": "stills",
        "image_quality": "low",
        "runway_max_credits": 220,
        "runtime_label": "SATOSHI_PREVIEW",
    },
    "production": {
        "publish": False,  # publication still requires explicit --publish
        "visual_mode": "ai",
        "image_quality": "high",
        "runway_max_credits": 650,
        "runtime_label": "SATOSHI_PRODUCTION",
    },
}

COMMON = {
    "voice_preset": "Clint",
    "character_id": "satoshi_shkreli_v1",
    "target_seconds": 55,
    "preferred_range_seconds": [52, 58],
    "hard_max_seconds": 60,
    "spoken_word_target": [115, 145],
    "visual_change_seconds": [2, 4],
    "editorial_sequence": [
        "hook",
        "reveal",
        "mechanism_or_context",
        "evidence_receipt",
        "satoshi_interpretation_or_reaction",
        "caveat",
        "consequence",
        "callback",
    ],
    "required_systems": [
        "canonical_satoshi_identity",
        "clint_voice",
        "research_and_source_receipts",
        "reusable_asset_library",
        "candidate_visual_coverage",
        "director_tournament",
        "evidence_cards",
        "remotion_assembly",
        "realism_recipe",
    ],
}


def write_contract(profile: str, publish: bool) -> Path:
    data = {
        "schema_version": 1,
        "engine": "satoshi_supervisor.py",
        "profile": profile,
        "publish": bool(publish),
        "common": COMMON,
        "profile_settings": PROFILES[profile],
    }
    target = Path("outputs/supervisor/runtime-contract.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PROFILES), required=True)
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()

    profile = PROFILES[args.profile]
    if args.profile == "preview" and args.publish:
        parser.error("Preview can never publish.")

    os.environ["SATOSHI_RUNTIME_PROFILE"] = args.profile
    os.environ["SATOSHI_RUNTIME_LABEL"] = profile["runtime_label"]
    os.environ["RUNWAY_VOICE_PRESET"] = COMMON["voice_preset"]
    os.environ["SATOSHI_VISUAL_MODE"] = profile["visual_mode"]
    os.environ["OPENAI_IMAGE_QUALITY"] = profile["image_quality"]
    os.environ["RUNWAY_MAX_CREDITS"] = str(profile["runway_max_credits"])
    os.environ["SATOSHI_AUTO_PUBLISH_INSTAGRAM"] = "true" if args.publish else "false"

    contract = write_contract(args.profile, args.publish)
    print(f"SATOSHI_RUNTIME_CONTRACT={contract}")

    cmd = ["python", "satoshi_supervisor.py"]
    if args.status_only:
        cmd.append("--status-only")
    return subprocess.run(cmd, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
