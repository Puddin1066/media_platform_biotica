"""Build a direct Remotion episode from the frozen Tetris EDL and R2 assets.

This path intentionally skips research/supervisor orchestration. It copies only
the selected generated assets into Remotion public assets, emits a simple
30-second voiceover-first episode manifest, and leaves the evidence slot as
native Remotion typography/source treatment.
"""
from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as src, path.open("wb") as dst:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            dst.write(chunk)


def _artifact_source(url: str, asset_root: Path, filename: str) -> Path:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if len(parts) < 2:
        raise ValueError(f"Cannot derive Runway job id from {url}")
    job_id = parts[-2]
    source = asset_root / "work" / job_id / filename
    if not source.is_file():
        raise FileNotFoundError(source)
    return source


def build(edl_path: str | Path, remotion_dir: str | Path = "remotion",
          asset_root: str | Path | None = None) -> Path:
    edl = json.loads(Path(edl_path).read_text(encoding="utf-8"))
    root = Path(remotion_dir)
    assets = root / "public" / "direct-assets"
    assets.mkdir(parents=True, exist_ok=True)

    srcmap = edl["sources"]
    mapping = {
        "hero_video": "hero.mp4",
        "memory_video": "memory.mp4",
        "software_video": "software.mp4",
        "engagement_video": "engagement.mp4",
        "dtx_still": "dtx.png",
        "discovery_still": "discovery.png",
    }
    asset_root_path = Path(asset_root) if asset_root else None
    for key, filename in mapping.items():
        target = assets / filename
        if target.exists():
            continue
        if asset_root_path:
            source_name = "0.mp4" if filename.endswith(".mp4") else "0.png"
            shutil.copyfile(_artifact_source(srcmap[key], asset_root_path, source_name), target)
        else:
            download(srcmap[key], target)

    beats = []
    for item in edl["timeline"]:
        asset = item.get("asset")
        inset_video = None
        still = ""
        visual_type = "illustration"
        source_label = "AI ILLUSTRATION"
        if asset == "hero_video":
            inset_video = "direct-assets/hero.mp4"
        elif asset == "memory_video":
            inset_video = "direct-assets/memory.mp4"
        elif asset == "software_video":
            inset_video = "direct-assets/software.mp4"
        elif asset == "engagement_video":
            inset_video = "direct-assets/engagement.mp4"
        elif asset == "dtx_still":
            still = "direct-assets/dtx.png"
        elif asset == "discovery_still":
            still = "direct-assets/discovery.png"
        else:
            visual_type = "typography"
            source_label = "RESEARCH / SOURCE RECEIPT"

        beats.append({
            "beat_id": item["id"],
            "role": item["role"],
            "text": item["screen_text"],
            "citations": [],
            "still": still,
            "inset_video": inset_video,
            "motion": item.get("motion", "hold"),
            "from": round(item["from_seconds"] * edl["fps"]),
            "duration": round(item["duration_seconds"] * edl["fps"]),
            "visual_type": visual_type,
            "screen_text": item["screen_text"],
            "source_label": source_label,
            "playback_rate": 1,
        })

    episode = {
        "title": "Latent digital therapeutics",
        "host": "",
        "voice": None,
        "loop_host": False,
        "cutaway_from_frame": 0,
        "beats": beats,
        "duration_frames": edl["target_seconds"] * edl["fps"],
        "fps": edl["fps"],
        "width": edl["width"],
        "height": edl["height"],
    }
    target = root / "public" / "direct-episode.json"
    target.write_text(json.dumps(episode, indent=2) + "\n", encoding="utf-8")
    return target


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--edl", default="production_specs/tetris_edit_decision.json")
    p.add_argument("--remotion-dir", default="remotion")
    p.add_argument("--asset-root")
    args = p.parse_args()
    print(build(args.edl, args.remotion_dir, args.asset_root))


if __name__ == "__main__":
    main()
