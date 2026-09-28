"""Produce the locked TRT pilot with joke-first AI visuals plus exact graphics.

The production spec is itself a valid five-beat unreviewed draft, so this runner
bypasses another LLM rewrite. Runway receives the locked narration and visual
briefs; Remotion assembles the host and generated cutaways; exact numeric and
company/mechanism graphics are then composited deterministically. Never publishes.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import deterministic_graphics
import episode
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


def run(spec_path, root, voice_id, avatar_id, live=False, render=False):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("status") != "review_required" or spec.get("format") != "short":
        raise ValueError("TRT pilot requires a locked review_required short spec")
    if spec.get("publishable") is not False:
        raise ValueError("Pilot spec must remain explicitly non-publishable")

    _install_pilot_visual_grammar()
    _preserve_natural_narration_duration()
    result = unreviewed_video_preview.run(
        spec_path, root, voice_id, avatar_id, live=live, render=render
    )

    if not render:
        return result

    final = Path("remotion/out/reel.mp4")
    if not final.is_file():
        raise RuntimeError("Base Remotion reel was not produced")
    base = Path("remotion/out/reel-base-before-exact-graphics.mp4")
    shutil.copyfile(final, base)
    decorated = Path("remotion/out/reel-with-exact-graphics.mp4")
    deterministic_graphics.apply_graphics(base, spec_path, decorated)
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
    p.add_argument("--avatar-id", required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    result = run(args.spec, args.input_dir, args.voice_id, args.avatar_id,
                 live=args.live, render=args.render)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
