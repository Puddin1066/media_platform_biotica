"""Lean Satoshi insets: Wikimedia Commons stills → short Remotion loops.

Canonical production should spend OpenAI on websearch + one Satoshi script pass,
and Runway on the host performance — not six Gen-4.5 inset generations per Reel.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import footage

USER_AGENT = "BioticaLeanVisuals/0.1"
STILL_SECONDS = 5


def _strip_html(value):
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _credit(row):
    artist = _strip_html(row.get("artist_html"))
    license_name = _strip_html(row.get("license_name")) or "Commons"
    title = _strip_html(row.get("title"))[:80]
    parts = [p for p in (title, artist, license_name) if p]
    return " / ".join(parts)[:180] or "Wikimedia Commons"


def query_for_slot(slot, draft_topic=""):
    """Build a Commons search from the visual-director slot + episode topic."""
    bits = [
        str(slot.get("overlay_text") or "").strip(),
        str(slot.get("visual_function") or "").strip().replace("_", " "),
        str(draft_topic or "").strip()[:80],
    ]
    query = " ".join(b for b in bits if b)
    return query[:120] or "science laboratory diagram"


def download_https(url, destination, max_bytes=40 * 1024 * 1024):
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("Commons media must use HTTPS")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=45) as src, part.open("wb") as out:
            if urllib.parse.urlparse(src.geturl()).scheme != "https":
                raise ValueError("Download redirected away from HTTPS")
            size = 0
            while chunk := src.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise ValueError("Commons download exceeds size cap")
                out.write(chunk)
        if size <= 0:
            raise ValueError("Empty Commons download")
        part.replace(destination)
        return size
    finally:
        part.unlink(missing_ok=True)


def still_to_loop_mp4(image_path, video_path, seconds=STILL_SECONDS):
    """Ken-Burns-free hold: encode a still as a silent vertical-friendly MP4."""
    image_path = Path(image_path)
    video_path = Path(video_path)
    video_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", str(image_path),
        "-t", str(seconds), "-r", "30",
        "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,"
               "pad=1280:720:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", str(video_path),
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0 or not video_path.is_file() or video_path.stat().st_size <= 0:
        raise RuntimeError("ffmpeg still→mp4 failed: " + (proc.stderr or "")[-800:])
    return video_path


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_commons_insets(root, direction, draft_topic="", live=False, discover=None):
    """Return six visual_result dicts compatible with unreviewed_video_preview.build_plan."""
    discover = discover or footage.discover_commons_images
    root = Path(root)
    out_dir = root / "generated" / "commons-visuals"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    catalog = []
    for index, slot in enumerate(direction["render_slots"]):
        cue = slot["cue_id"]
        query = query_for_slot(slot, draft_topic)
        if not live:
            rel = f"generated/commons-visuals/{cue}-dry.mp4"
            results.append({
                "state": "dry_run",
                "candidate": {
                    "id": f"commons-dry:{cue}",
                    "cue_id": cue,
                    "media_source": rel,
                    "provider": "commons",
                    "search_query": query,
                },
                "rights_status": "review_required",
                "license_basis": "Wikimedia Commons still (dry-run placeholder)",
                "credit": "COMMONS STILL (DRY RUN)",
                "visual_type": "source",
            })
            continue

        rows = discover(query, limit=8)
        if not rows:
            rows = discover((draft_topic or "biomedical research")[:80], limit=8)
        if not rows:
            raise RuntimeError(f"No Commons image candidates for cue {cue!r} query {query!r}")
        chosen = rows[0]
        stem = f"{index:02d}-{cue}"
        image_path = out_dir / f"{stem}.img"
        video_path = out_dir / f"{stem}.mp4"
        meta_path = out_dir / f"{stem}.json"
        download_https(chosen["direct_url"], image_path)
        still_to_loop_mp4(image_path, video_path)
        rel = str(video_path.relative_to(root))
        candidate = {
            "id": chosen["id"] + ":" + _sha(video_path)[:12],
            "cue_id": cue,
            "media_source": rel,
            "provider": "commons",
            "page_url": chosen.get("page_url"),
            "search_query": query,
            "source_title": chosen.get("title"),
            "license_name": chosen.get("license_name"),
        }
        packet = {
            "state": "collected",
            "candidate": candidate,
            "rights_status": "review_required",
            "license_basis": chosen.get("license_name") or "Wikimedia Commons",
            "credit": _credit(chosen),
            "visual_type": "source",
            "source": chosen,
        }
        meta_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        catalog.append(candidate)
        results.append(packet)
    (out_dir / "catalog.json").write_text(
        json.dumps({"schema_version": 1, "topic": draft_topic, "candidates": catalog},
                   indent=2) + "\n",
        encoding="utf-8")
    return results
