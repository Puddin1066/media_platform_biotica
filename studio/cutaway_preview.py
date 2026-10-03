"""Finish an explicitly requested editorial preview using completed host footage.

This helper never calls Runway and never retries a rejected task. It keeps only
the contiguous successful opening, then tells Remotion to hide the host and
expand the existing illustrations. The approved narration remains unchanged.
"""
import argparse
import json
import math
from pathlib import Path
import media_store
import runway_media
import plate_host
import studio_media
from studio import module_runner as runner

def prepare(root, episode):
    root = Path(root)
    if runner.load_manifest(episode)["modules"]["assets"]["status"] != "completed":
        raise ValueError("Finish and review assets before editorial cutaway assembly")
    artifacts, work = studio_media.paths(root, episode)
    records = [json.loads(p.read_text()) for p in (artifacts / "runway_host_jobs").glob("*/result.json")]
    tasks = sorted((r for r in records if r.get("operation") == "post_character_performance"),
                   key=lambda r: r.get("provider_detail", {}).get("createdAt", ""))
    # Only a contiguous successful prefix may play against the original voice.
    # Later successes cannot be moved to an earlier point in the narration.
    prefix = []
    for task in tasks:
        if task.get("state") != "completed":
            break
        prefix.append(task)
    failures = [r for r in tasks if r.get("state") == "failed"]
    if not prefix or not failures:
        raise ValueError("Editorial cutaway requires a completed host prefix and documented failure")
    if not any(r.get("provider_detail", {}).get("failureCode", "").startswith("SAFETY.") for r in failures):
        raise ValueError("Inspect non-moderation failures before choosing an editorial cutaway")
    audio, ref = studio_media.selected_audio(artifacts, work / "cutaway")
    script = studio_media.read(artifacts / "canonical_script.json")
    timing = studio_media.validate_alignment(artifacts, script, ref["sha256"])
    parts = []
    for index, task in enumerate(prefix):
        media = task["media"][0]
        target = work / "cutaway" / f"part-{index}.mp4"
        fetched = media_store.fetch(media["key"], target)
        if fetched["sha256"] != media["sha256"]:
            raise ValueError("Completed host checksum mismatch")
        parts.append(target)
    target = work / "cutaway" / "opening.mp4"
    plate_host._concat_silent(parts, target)
    cutoff = min(math.floor(runway_media.duration(target) * 30), math.ceil(timing["duration_ms"] * .03))
    if cutoff <= 0:
        raise ValueError("No playable host footage")
    media = media_store.persist(target, f"satoshi-studio/{episode}/host/editorial-opening-{ref['sha256']}.mp4")
    manifest_path = studio_media.write(artifacts / "host_manifest.json", {
        "generated": True, "mode": "editorial_cutaway", "media": media,
        "audio_sha256": ref["sha256"], "loop": False, "cutaway_from_frame": cutoff,
        "lip_sync": "partial_speech_driven_editorial_cutaways",
        "completed_performance_task_ids": [r["response"]["id"] for r in prefix],
        "failed_task_ids": [r["response"]["id"] for r in failures],
        "note": "Completed speaking opening only; full-frame evidence visuals after cutoff. No rejected task was retried and no new provider task was submitted."
    })
    manifest = runner.load_manifest(episode)
    runner.complete(episode, manifest, "host", [str(manifest_path.relative_to(root))])
    print(json.dumps({"opening_seconds": cutoff / 30, "total_seconds": timing["duration_ms"] / 1000}))
    return cutoff

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--episode", required=True)
    args = ap.parse_args()
    prepare(runner.ROOT, args.episode)
