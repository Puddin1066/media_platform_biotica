"""Validate Satoshi persona-scene and visible-speech contracts before render."""
from __future__ import annotations
import json
from pathlib import Path

def validate_episode_manifest(manifest: dict) -> list[str]:
    errors=[]
    scene=manifest.get("persona_scene")
    if not isinstance(scene,dict):
        return ["missing required persona_scene"]
    required=["scene_id","persona_lore_id","environment","wardrobe","persona_hook","pivot_line","why_this_setting_fits"]
    for key in required:
        if not str(scene.get(key) or "").strip():
            errors.append(f"persona_scene missing {key}")
    env=str(scene.get("environment") or "").lower()
    wardrobe=str(scene.get("wardrobe") or "").lower()
    if env in {"studio","neutral studio","generic office","office"}:
        errors.append("persona_scene uses forbidden generic environment")
    if wardrobe=="suit":
        errors.append("persona_scene uses forbidden generic suit default")
    beats=manifest.get("beats") or []
    speaking=0
    for beat in beats:
        visible=bool(beat.get("on_camera_satoshi"))
        spoken=bool(beat.get("spoken_by_satoshi"))
        audio=bool(beat.get("spoken_text") or beat.get("text"))
        synced=bool(beat.get("host_performance_asset") or beat.get("requires_lip_sync") is False)
        if visible and spoken:
            speaking+=1
            if not audio:
                errors.append(f"{beat.get('beat_id','unknown')}: visible speaking beat has no spoken text")
            if not synced:
                errors.append(f"{beat.get('beat_id','unknown')}: visible speaking beat lacks synced host performance")
        if visible and not spoken and beat.get("narration_underlay"):
            errors.append(f"{beat.get('beat_id','unknown')}: silent Satoshi reaction cannot carry narration")
    if speaking < 1:
        errors.append("episode has no visible Satoshi speaking beat")
    return errors

def main():
    import argparse
    p=argparse.ArgumentParser()
    p.add_argument("manifest")
    a=p.parse_args()
    manifest=json.loads(Path(a.manifest).read_text())
    errors=validate_episode_manifest(manifest)
    if errors:
        raise SystemExit("\n".join(errors))
    print("persona direction valid")

if __name__=="__main__":
    main()
