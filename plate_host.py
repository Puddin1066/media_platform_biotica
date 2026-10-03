"""Build a speech-synced host from an uploaded plate without a new avatar ID.

A single persistent Runway driver avatar supplies speech/body performance for each
narration beat. Act Two transfers that performance onto the newly supplied plate.
The uploaded plate therefore changes episode-to-episode while RUNWAY_AVATAR_ID
remains a stable internal driver. Outputs are private preview assets only.
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import time
from pathlib import Path

import episode
import runway_media
import runway_host
from speech_timing import BEATS
from studio import digest

POLL_SECONDS = 15
TIMEOUT_SECONDS = 1800
ACT_TWO_CREDITS_PER_SECOND = 5
DEFAULT_PLATE_HOST_MAX_CREDITS = 650


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


def _budget(audio_files):
    seconds = [runway_media.duration(path) for path in audio_files]
    # Existing avatar-videos pricing contract in this repository is bounded as
    # 2 upfront + 2 per six seconds. Act Two is 5 credits/second.
    driver = sum(2 + 2 * math.ceil(value / 6) for value in seconds)
    act_two = math.ceil(sum(seconds) * ACT_TWO_CREDITS_PER_SECOND)
    estimate = driver + act_two
    cap = int(os.environ.get("PLATE_HOST_MAX_CREDITS", str(DEFAULT_PLATE_HOST_MAX_CREDITS)))
    if estimate > cap:
        raise RuntimeError(
            f"Uploaded-plate host spend governor blocked provider calls: {estimate} estimated credits exceeds {cap}"
        )
    return {"driver_avatar": driver, "act_two": act_two, "total_max": estimate, "cap": cap,
            "narration_seconds": sum(seconds)}


def ensure_local_mp4_plate(source, destination):
    """Accept a local MOV/MP4 plate and normalize to MP4 for Act Two."""
    source = Path(source)
    destination = Path(destination)
    if not source.is_file():
        raise ValueError("Uploaded character plate file is missing")
    suffix = source.suffix.lower()
    if suffix not in {".mp4", ".mov"}:
        raise ValueError("Uploaded character plate must be a local MP4 or MOV")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".mp4" and source.resolve() == destination.resolve():
        return destination
    if suffix == ".mp4":
        destination.write_bytes(source.read_bytes())
        return destination
    subprocess.run([
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-i", str(source), "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(destination),
    ], check=True, timeout=600)
    return destination


def install_uploaded_plate_host(root, plate_source, driver_avatar_id, live=False,
                                plate_r2_key=None):
    """Route episode.submit_host/collect_host through an uploaded plate.

    Returns (original_submit, original_collect) so callers can restore hooks.
    `plate_source` is a local MOV/MP4 path. When missing and live, `plate_r2_key`
    is fetched into the episode directory first.
    """
    import episode
    import media_store

    root = Path(root)
    character = root / "uploaded-character-plate.mp4"
    if plate_source:
        ensure_local_mp4_plate(plate_source, character)
    elif live and plate_r2_key:
        if not character.is_file():
            media_store.fetch(plate_r2_key, character)
        ensure_local_mp4_plate(character, character)
    elif not character.is_file():
        raise ValueError("uploaded_plate host mode requires plate_local_path or plate_r2_key")

    original_submit = episode.submit_host
    original_collect = episode.collect_host

    def submit_override(root_value, mode, live=False, avatar_id=None,
                        character_path=None, performance=None):
        result = build(
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


def build(root, character_plate, driver_avatar_id, live=False, aleph=None):
    """Create generated/host.mp4 using one stable driver avatar and a new plate."""
    root = Path(root)
    character_plate = ensure_local_mp4_plate(
        character_plate, root / "uploaded-character-plate.mp4")
    if not driver_avatar_id:
        raise ValueError("A persistent driver avatar ID is required internally")

    ledger = root / "generated" / "runway"
    ledger.mkdir(parents=True, exist_ok=True)
    driver_dir = root / "generated" / "plate-driver"
    host_dir = root / "generated" / "plate-host-beats"
    driver_dir.mkdir(parents=True, exist_ok=True)
    host_dir.mkdir(parents=True, exist_ok=True)

    audio_files = []
    for beat in BEATS:
        audio = episode.beat_file(root, beat)
        if audio is None:
            raise ValueError(f"Missing collected narration audio for {beat}")
        if runway_media.duration(audio) > 30:
            raise ValueError(f"Narration beat {beat} exceeds the 30-second driver limit")
        audio_files.append(audio)
    budget = _budget(audio_files)
    if aleph:
        budget["aleph"] = math.ceil(float(aleph.get("seconds", 10)) * 28)
        budget["total_max"] += budget["aleph"]
        if budget["total_max"] > budget["cap"]:
            raise ValueError("Aleph and Act Two exceed PLATE_HOST_MAX_CREDITS")

    plate_record = None
    if aleph and live:
        character_plate, plate_record = runway_host.prepare_plate(
            character_plate, aleph, root / "generated/runway-host-artifacts", root / "generated/runway-host-media")
    outputs = []
    for beat, audio in zip(BEATS, audio_files):
        driver = driver_dir / f"{beat}.mp4"
        host = host_dir / f"{beat}.mp4"
        if not driver.is_file():
            _submit_or_reuse_avatar(audio, ledger, driver_avatar_id, driver, live)
        if not host.is_file():
            if aleph and live:
                generated, _ = runway_host.perform_segment(
                    character_plate, driver, {}, root / "generated/runway-host-artifacts", root / "generated/runway-host-media")
                host.write_bytes(generated.read_bytes())
            else:
                _submit_or_reuse_act_two(character_plate, driver, ledger, host, live)
        if not host.is_file():
            return {"state": "dry_run", "beat": beat, "budget": budget,
                    "publishable": False}
        outputs.append(host)

    final = root / "generated" / "host.mp4"
    _concat_silent(outputs, final)
    metadata = {
        "schema_version": 1,
        "mode": "uploaded_plate_via_stable_driver",
        "character_sha256": runway_media.digest_file(character_plate),
        "driver_avatar_id": driver_avatar_id,
        "aleph_plate": plate_record,
        "beats": [str(p.relative_to(root)) for p in outputs],
        "host_sha256": runway_media.digest_file(final),
        "budget": budget,
        "publishable": False,
    }
    (root / "generated" / "plate-host.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return {"state": "collected", "file": str(final), "metadata": metadata,
            "publishable": False}
