"""Canonical Satoshi runtime with native Runway host audio preserved for lip sync.

The underlying canonical runtime remains the story/production orchestrator. This
wrapper changes only the final media handoff: avatar host clips keep the audio
Runway generated against their mouth motion, timing is derived from those host
clips, and Remotion does not replace that audio with a separately concatenated
narration track.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import canonical_satoshi_runtime as base
import render_audio_guard
import runway_media

_ORIGINAL_PREPARE_REMOTION = base.prepare_remotion


def concat_host_with_native_audio(parts, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    listing = destination.with_suffix(".concat.txt")
    listing.write_text(
        "".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in parts),
        encoding="utf-8",
    )
    try:
        subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing),
            "-vf", "scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "192k",
            "-ar", "48000", "-ac", "2", "-movflags", "+faststart",
            str(destination),
        ], check=True, timeout=1800)
    finally:
        listing.unlink(missing_ok=True)
    return destination


def timing_from_host_when_available(root, production, story):
    """Use generated avatar clip duration as timing authority when available."""
    root = Path(root)
    fps = 30
    role_lookup = {beat["role"]: beat for beat in story["beats"]}
    production_timing = []
    story_timing = []
    cursor = 0.0
    for block in production:
        cue = block["cue_id"]
        host_part = root / "generated" / "avatar-host-beats" / f"{cue}.mp4"
        audio = root / "audio" / f"{cue}.mp3"
        authority = host_part if host_part.is_file() else audio
        duration = runway_media.duration(authority)
        production_timing.append({
            "cue_id": cue,
            "start": cursor,
            "duration": duration,
            "timing_authority": "runway_host" if host_part.is_file() else "narration_audio",
        })
        children = [role_lookup[r] for r in block["story_roles"]]
        weights = [max(1, len(child["spoken_text"].split())) for child in children]
        total = sum(weights)
        child_cursor = cursor
        for index, (child, weight) in enumerate(zip(children, weights)):
            child_duration = (
                duration - (child_cursor - cursor)
                if index == len(children) - 1
                else duration * weight / total
            )
            story_timing.append({
                "beat_id": child["beat_id"],
                "role": child["role"],
                "start": child_cursor,
                "duration": child_duration,
            })
            child_cursor += child_duration
        cursor += duration
    return {
        "fps": fps,
        "duration_seconds": cursor,
        "production": production_timing,
        "story": story_timing,
    }


def prepare_remotion_native_audio(root, story, production, timing, stills, host_file, voice_file):
    """Package the audit narration but tell Remotion to play host-native audio."""
    payload = _ORIGINAL_PREPARE_REMOTION(
        root, story, production, timing, stills, host_file, voice_file
    )
    payload["voice"] = ""
    Path("remotion/public/canonical-episode.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path(root, "remotion-episode.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def render_reel_native_audio():
    subprocess.run([
        "npx", "remotion", "render", "src/index.ts", "CanonicalSatoshiEpisode",
        "out/canonical-reel.mp4",
    ], cwd="remotion", check=True, timeout=1800)
    video = Path("remotion/out/canonical-reel.mp4")
    if not video.is_file() or video.stat().st_size <= 0:
        raise RuntimeError("Remotion did not produce canonical-reel.mp4")
    stats = render_audio_guard.validate(video)
    print(json.dumps({"native_host_audio": stats}, indent=2, sort_keys=True))
    return video


def install_native_lipsync_overrides():
    base._concat_host = concat_host_with_native_audio
    base._timing = timing_from_host_when_available
    base.prepare_remotion = prepare_remotion_native_audio
    base.render_reel = render_reel_native_audio


def main():
    install_native_lipsync_overrides()
    base.main()


if __name__ == "__main__":
    main()
