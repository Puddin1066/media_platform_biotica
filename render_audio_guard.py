"""Guarantee that the final reel carries audible master narration.

Remotion remains responsible for picture composition. After Remotion renders,
this script explicitly remuxes the packaged narration track over the rendered
video, normalizes it to a speech-friendly level, and validates the resulting
MP4. A production run must fail rather than report success when narration is
missing, inaudible, malformed, or badly out of sync.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
from pathlib import Path


class AudioValidationError(RuntimeError):
    pass


def _run(args):
    proc = subprocess.run(args, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "command failed").strip())
    return proc.stdout, proc.stderr


def probe(path: Path):
    stdout, _ = _run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format",
        "-of", "json", str(path),
    ])
    return json.loads(stdout)


def duration_seconds(path: Path) -> float:
    info = probe(path)
    value = info.get("format", {}).get("duration")
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise AudioValidationError(f"Could not determine duration for {path}")
    if not math.isfinite(result) or result <= 0:
        raise AudioValidationError(f"Invalid duration for {path}")
    return result


def volume_stats(path: Path):
    proc = subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
        "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-",
    ], text=True, capture_output=True)
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    mean_match = re.search(r"mean_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB", text)
    max_match = re.search(r"max_volume:\s*(-?(?:\d+(?:\.\d+)?|inf))\s*dB", text)
    if not mean_match or not max_match:
        raise AudioValidationError("Rendered MP4 does not expose measurable audio energy")

    def parse(value):
        return float("-inf") if value == "-inf" else float(value)

    return parse(mean_match.group(1)), parse(max_match.group(1))


def validate(video: Path, narration: Path | None = None):
    info = probe(video)
    streams = info.get("streams", [])
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise AudioValidationError("Final reel has no video stream")
    if len(audio_streams) != 1:
        raise AudioValidationError("Final reel must contain exactly one master audio stream")

    audio = audio_streams[0]
    if audio.get("codec_name") != "aac":
        raise AudioValidationError("Final reel master audio must be AAC")
    if str(audio.get("sample_rate")) != "48000":
        raise AudioValidationError("Final reel master audio must be 48 kHz")
    if int(audio.get("channels") or 0) != 2:
        raise AudioValidationError("Final reel master audio must be stereo")

    mean_db, max_db = volume_stats(video)
    if not math.isfinite(mean_db) or not math.isfinite(max_db):
        raise AudioValidationError("Final reel audio is silent")
    if mean_db < -42 or max_db < -18:
        raise AudioValidationError(
            f"Final reel narration is too quiet (mean {mean_db:.1f} dB, max {max_db:.1f} dB)"
        )

    video_duration = duration_seconds(video)
    if narration is not None:
        narration_duration = duration_seconds(narration)
        if abs(video_duration - narration_duration) > 0.75:
            raise AudioValidationError(
                "Final reel and narration durations diverge by more than 0.75 seconds "
                f"({video_duration:.3f}s vs {narration_duration:.3f}s)"
            )

    return {
        "video_seconds": video_duration,
        "mean_volume_db": mean_db,
        "max_volume_db": max_db,
        "audio_codec": audio.get("codec_name"),
        "sample_rate": int(audio.get("sample_rate")),
        "channels": int(audio.get("channels")),
        "status": "audible_master_narration_confirmed",
    }


def mux_master_narration(video: Path, narration: Path):
    video = video.resolve(strict=True)
    narration = narration.resolve(strict=True)
    if video.suffix.lower() != ".mp4":
        raise ValueError("Rendered reel must be an MP4")
    if narration.suffix.lower() not in {".wav", ".mp3", ".m4a"}:
        raise ValueError("Narration must be WAV, MP3, or M4A")

    target = video.with_suffix(".master-audio.mp4")
    target.unlink(missing_ok=True)
    try:
        _run([
            "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(video), "-i", str(narration),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-c:a", "aac", "-profile:a", "aac_low", "-b:a", "192k",
            "-ar", "48000", "-ac", "2",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            "-movflags", "+faststart",
            "-map_metadata", "0",
            str(target),
        ])
        stats = validate(target, narration)
        target.replace(video)
        return stats
    finally:
        target.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True)
    parser.add_argument("--narration", required=True)
    args = parser.parse_args()
    stats = mux_master_narration(Path(args.video), Path(args.narration))
    print(json.dumps(stats, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
