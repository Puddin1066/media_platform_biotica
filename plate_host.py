"""Build a speech-synced host from an uploaded plate without a new avatar ID.

A single persistent Runway driver avatar supplies speech/body performance for each
narration beat. Act Two transfers that performance onto the newly supplied plate.
The uploaded plate therefore changes episode-to-episode while RUNWAY_AVATAR_ID
remains a stable internal driver. Outputs are private preview assets only.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import episode
import runway_media
from speech_timing import BEATS
from studio import digest

POLL_SECONDS = 15
TIMEOUT_SECONDS = 1800


def _existing_record(ledger, specification):
    target = ledger / (digest(specification) + ".json")
    if target.exists():
        return target
    for path in ledger.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("specification") == specification:
            return path
    return None


def _collect_until_ready(record, destination):
    record = Path(record)
    destination = Path(destination)
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        data = json.loads(record.read_text(encoding="utf-8"))
        state = data.get("state")
        if state == "collected":
            existing = Path(data.get("file", ""))
            if existing.is_file():
                if existing.resolve() != destination.resolve():
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(existing.read_bytes())
                return destination
        if state in {"failed", "cancelled", "rejected_no_task", "reserved_unknown"}:
            raise RuntimeError(f"Runway host task cannot continue: {state}")
        result = runway_media.collect(record, destination)
        if result.get("state") == "collected":
            return destination
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Timed out waiting for Runway task {data.get('task_id')}")
        time.sleep(POLL_SECONDS)


def _submit_or_reuse_avatar(audio, ledger, driver_avatar_id, destination, live):
    preview = runway_media.submit_avatar(driver_avatar_id, audio, ledger, live=False)
    existing = _existing_record(ledger, preview["specification"])
    if existing:
        return _collect_until_ready(existing, destination)
    if not live:
        return None
    submitted = runway_media.submit_avatar(driver_avatar_id, audio, ledger, live=True)
    return _collect_until_ready(submitted["record"], destination)


def _submit_or_reuse_act_two(character, performance, ledger, destination, live):
    preview = runway_media.submit_act_two(character, performance, ledger, live=False)
    existing = _existing_record(ledger, preview["specification"])
    if existing:
        return _collect_until_ready(existing, destination)
    if not live:
        return None
    submitted = runway_media.submit_act_two(character, performance, ledger, live=True)
    return _collect_until_ready(submitted["record"], destination)


def _concat_silent(parts, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    listing = destination.with_suffix(".concat.txt")
    listing.write_text("".join(f"file '{Path(p).resolve().as_posix()}'\n" for p in parts), encoding="utf-8")
    try:
        subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(listing), "-an",
            "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2",
            "-r", "30", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(destination),
        ], check=True, timeout=1800)
    finally:
        listing.unlink(missing_ok=True)
    return destination


def build(root, character_plate, driver_avatar_id, live=False):
    """Create generated/host.mp4 using one stable driver avatar and a new plate."""
    root = Path(root)
    character_plate = Path(character_plate)
    if not character_plate.is_file() or character_plate.suffix.lower() != ".mp4":
        raise ValueError("Uploaded character plate must be a local MP4")
    if not driver_avatar_id:
        raise ValueError("A persistent driver avatar ID is required internally")

    ledger = root / "generated" / "runway"
    ledger.mkdir(parents=True, exist_ok=True)
    driver_dir = root / "generated" / "plate-driver"
    host_dir = root / "generated" / "plate-host-beats"
    driver_dir.mkdir(parents=True, exist_ok=True)
    host_dir.mkdir(parents=True, exist_ok=True)

    outputs = []
    for beat in BEATS:
        audio = episode.beat_file(root, beat)
        if audio is None:
            raise ValueError(f"Missing collected narration audio for {beat}")
        if runway_media.duration(audio) > 30:
            raise ValueError(f"Narration beat {beat} exceeds the 30-second driver limit")
        driver = driver_dir / f"{beat}.mp4"
        host = host_dir / f"{beat}.mp4"
        if not driver.is_file():
            _submit_or_reuse_avatar(audio, ledger, driver_avatar_id, driver, live)
        if not host.is_file():
            _submit_or_reuse_act_two(character_plate, driver, ledger, host, live)
        if not host.is_file():
            return {"state": "dry_run", "beat": beat, "publishable": False}
        outputs.append(host)

    final = root / "generated" / "host.mp4"
    _concat_silent(outputs, final)
    metadata = {
        "schema_version": 1,
        "mode": "uploaded_plate_via_stable_driver",
        "character_sha256": runway_media.digest_file(character_plate),
        "driver_avatar_id": driver_avatar_id,
        "beats": [str(p.relative_to(root)) for p in outputs],
        "host_sha256": runway_media.digest_file(final),
        "publishable": False,
    }
    (root / "generated" / "plate-host.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {"state": "collected", "file": str(final), "metadata": metadata,
            "publishable": False}
