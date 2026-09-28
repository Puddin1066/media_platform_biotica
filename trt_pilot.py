"""Produce the locked TRT pilot with joke-first AI visuals plus exact graphics.

The production spec is itself a valid five-beat unreviewed draft, so this runner
bypasses another LLM rewrite. Runway receives the locked narration and visual
briefs; Remotion assembles the host and generated cutaways; exact numeric and
company/mechanism graphics are then composited deterministically. Never publishes.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import deterministic_graphics
import episode
import media_store
import plate_host
import unreviewed_video_preview
import visual_director


def _install_pilot_visual_grammar():
    """Ban the generic office/paper visual grammar for this production test."""
    visual_director.SHOT_GRAMMARS["evidence_receipt"].update({
        "composition": "bold data-native composition with one immediately legible result, symbol, chart shape, or regulatory motif; no desk and no loose papers",
        "camera": "direct graphic reveal or controlled punch-in, never a slow office-table push",
        "subject_motion": "one kinetic transformation tied literally to the spoken claim",
        "environment_motion": "minimal; preserve immediate comprehension",
        "lighting": "high-contrast editorial explainer lighting",
        "aesthetic": "kinetic premium science explainer with dry visual-comedy energy",
        "energy": "high",
        "literalness": "conceptual illustration only; exact names and numbers are added later by deterministic graphics",
        "overlay_safe_area": "keep the left/top evidence window clear for deterministic sourced typography",
        "timing": "0-1s pattern interrupt; 1-3s reveal the mechanism or metaphor; 3-5s clean hold for exact overlay",
    })
    visual_director.SHOT_GRAMMARS["absurd_contrast"].update({
        "aesthetic": "deadpan premium visual satire with social-video punch, not generic commercial B-roll",
        "timing": "0-1.5s establish; 1.5-3s visual punchline; 3-5s reaction/callback hold",
    })
    visual_director.SHOT_GRAMMARS["personal_consequence"].update({
        "aesthetic": "clean visual metaphor or mechanism animation, immediately legible on a phone",
        "composition": "single bold metaphor or mechanism with strong silhouette and no office setting",
    })


def _preserve_natural_narration_duration():
    """Pilot narration is the master clock; never time-compress it to 30 seconds."""
    episode._fit_unreviewed_preview_audio = lambda root, files: files


def _install_uploaded_plate_host(root, plate_r2_key, driver_avatar_id, live):
    """Temporarily route the normal host stage through an uploaded R2 plate.

    The stable avatar ID is only a hidden performance driver. A new avatar ID is
    not created or requested for each plate.
    """
    if not plate_r2_key:
        raise ValueError("uploaded_plate host mode requires a non-empty plate R2 key")
    root = Path(root)
    character = root / "uploaded-character-plate.mp4"
    if live and not character.is_file():
        media_store.fetch(plate_r2_key, character)
    original_submit = episode.submit_host
    original_collect = episode.collect_host

    def submit_override(root_value, mode, live=False, avatar_id=None,
                        character=None, performance=None):
        result = plate_host.build(
            root_value, root / "uploaded-character-plate.mp4",
            driver_avatar_id or avatar_id, live=live,
        )
        marker = Path(root_value) / "generated" / "plate-host.json"
        return {"state": result.get("state"), "record": str(marker),
                "task_id": None, "plate_host": True}

    def collect_override(root_value, record_name):
        host = Path(root_value) / "generated" / "host.mp4"
        if not host.is_file():
            raise RuntimeError("Uploaded plate host did not produce generated/host.mp4")
        return {"state": "collected", "task_id": None, "file": str(host)}

    episode.submit_host = submit_override
    episode.collect_host = collect_override
    return original_submit, original_collect


def run(spec_path, root, voice_id, avatar_id, live=False, render=False,
        host_mode="avatar", plate_r2_key=None):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("status") != "review_required" or spec.get("format") != "short":
        raise ValueError("TRT pilot requires a locked review_required short spec")
    if spec.get("publishable") is not False:
        raise ValueError("Pilot spec must remain explicitly non-publishable")
    if host_mode not in {"avatar", "uploaded_plate"}:
        raise ValueError("host_mode must be avatar or uploaded_plate")

    _install_pilot_visual_grammar()
    _preserve_natural_narration_duration()
    originals = None
    try:
        if host_mode == "uploaded_plate":
            originals = _install_uploaded_plate_host(root, plate_r2_key, avatar_id, live)
        result = unreviewed_video_preview.run(
            spec_path, root, voice_id, avatar_id, live=live, render=render
        )
    finally:
        if originals:
            episode.submit_host, episode.collect_host = originals

    result["host_mode"] = host_mode
    if plate_r2_key:
        result["plate_r2_key"] = plate_r2_key

    if not render:
        return result

    final = Path("remotion/out/reel.mp4")
    if not final.is_file():
        raise RuntimeError("Base Remotion reel was not produced")
    base = Path("remotion/out/reel-base-before-exact-graphics.mp4")
    shutil.copyfile(final, base)
    decorated = Path("remotion/out/reel-with-exact-graphics.mp4")
    timing_path = Path(root) / "generated" / "timing.json"
    if not timing_path.is_file():
        raise RuntimeError("Measured narration timing was not produced")
    deterministic_graphics.apply_graphics(
        base, spec_path, decorated, timing_path=timing_path
    )
    decorated.replace(final)

    root_path = Path(root)
    distribution = {
        "schema_version": 1,
        "entities": spec.get("distribution_entities", []),
        "rule": "resolve and verify official handles at publish-review time; never invent handles",
        "max_direct_mentions": 4,
        "max_hashtags": 8,
        "publishable": False,
    }
    (root_path / "distribution-metadata.json").write_text(
        json.dumps(distribution, indent=2) + "\n", encoding="utf-8"
    )
    result["deterministic_graphics"] = True
    result["final_mp4"] = str(final)
    result["publishable"] = False
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec", default="production_specs/trt_cardiovascular_pilot.json")
    p.add_argument("--input-dir", default="outputs/trt-pilot")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--avatar-id", required=True,
                   help="Persistent internal driver avatar; reused across uploaded plates")
    p.add_argument("--host-mode", choices=("avatar", "uploaded_plate"),
                   default=os.environ.get("SATOSHI_HOST_MODE", "avatar"))
    p.add_argument("--plate-r2-key", default=os.environ.get("SATOSHI_PLATE_R2_KEY"))
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    result = run(args.spec, args.input_dir, args.voice_id, args.avatar_id,
                 live=args.live, render=args.render,
                 host_mode=args.host_mode, plate_r2_key=args.plate_r2_key)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
