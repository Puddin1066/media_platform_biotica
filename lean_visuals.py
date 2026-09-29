"""Lean Satoshi insets: Wikimedia Commons stills → short Remotion loops.

Canonical production should spend OpenAI on websearch + one Satoshi script pass,
and Runway on the host performance — not six Gen-4.5 inset generations per Reel.

Commons queries must be short noun phrases that return images. Overlay slogans
and truncated topic sentences return empty result sets and waste the produce run.
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

# visual_function → Commons-friendly seed (tested to return bitmap hits).
FUNCTION_SEEDS = {
    "pattern_interrupt": "fingerstick blood test laboratory",
    "absurd_contrast": "blood collection tube laboratory",
    "personal_consequence": "phlebotomy blood draw clinic",
    "scale_or_intensify": "microliter pipette laboratory",
    "evidence_receipt": "PCR gel electrophoresis",
    "annotation_or_punch_in": "scientific journal article laboratory",
    "contrast_reset": "diagnostic laboratory instrument",
    "limitation_overlay": "medical laboratory research",
    "callback_visual": "Raman spectroscopy laboratory",
    "reaction_or_end_card": "clinical chemistry laboratory",
}

GENERIC_FALLBACKS = [
    "blood test laboratory",
    "PCR gel electrophoresis",
    "Raman spectroscopy laboratory",
    "medical laboratory microscope",
    "phlebotomy blood draw",
    "scientific research laboratory",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "vs", "versus", "of", "to", "for", "from",
    "with", "without", "can", "does", "is", "are", "be", "that", "this", "than",
    "into", "on", "in", "by", "as", "it", "its", "not", "no", "yes", "how",
    "what", "which", "when", "where", "why", "who", "better", "more", "most",
}


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


def _topic_keywords(draft_topic, limit=4):
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", str(draft_topic or ""))
    kept = []
    seen = set()
    for word in words:
        key = word.casefold()
        if key in STOPWORDS or key in seen:
            continue
        seen.add(key)
        kept.append(word)
        if len(kept) >= limit:
            break
    return kept


def query_for_slot(slot, draft_topic=""):
    """Build a short Commons noun-phrase search — never paste spoken overlay text."""
    function = str(slot.get("visual_function") or "").strip()
    seed = FUNCTION_SEEDS.get(function) or function.replace("_", " ").strip()
    keywords = _topic_keywords(draft_topic, limit=3)
    # Prefer seed alone when topic keywords would make the query too specific/empty.
    query = seed
    if keywords:
        # Keep one topical word (e.g. Haemanthus / Raman / PCR) when useful.
        topical = next(
            (w for w in keywords if w.casefold() not in seed.casefold()),
            None,
        )
        if topical:
            query = f"{seed} {topical}"
    return (query or "science laboratory")[:120]


def queries_for_slot(slot, draft_topic=""):
    """Ordered search attempts for one slot: primary then generic ladder."""
    primary = query_for_slot(slot, draft_topic)
    seen = {primary.casefold()}
    out = [primary]
    for fallback in GENERIC_FALLBACKS:
        key = fallback.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(fallback)
    return out


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


def _pick_row(rows, used_ids):
    for row in rows:
        if row.get("id") not in used_ids:
            return row
    return rows[0] if rows else None


def collect_commons_insets(root, direction, draft_topic="", live=False, discover=None):
    """Return six visual_result dicts compatible with unreviewed_video_preview.build_plan."""
    discover = discover or footage.discover_commons_images
    root = Path(root)
    out_dir = root / "generated" / "commons-visuals"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    catalog = []
    used_ids = set()
    for index, slot in enumerate(direction["render_slots"]):
        cue = slot["cue_id"]
        attempts = queries_for_slot(slot, draft_topic)
        query = attempts[0]
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

        chosen = None
        used_query = query
        for attempt in attempts:
            rows = discover(attempt, limit=8)
            pick = _pick_row(rows, used_ids)
            if pick:
                chosen = pick
                used_query = attempt
                break
        if not chosen:
            raise RuntimeError(
                f"No Commons image candidates for cue {cue!r} after queries {attempts!r}"
            )
        used_ids.add(chosen["id"])
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
            "search_query": used_query,
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
