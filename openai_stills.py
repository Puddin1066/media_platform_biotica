"""OpenAI still insets for Satoshi Reels.

Six topic-matched still images → ffmpeg 5s silent MP4s for the Remotion
evidence window. Spends OpenAI image credits (cents), not Runway Gen-4.5
(~360 credits for six 5s videos).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import lean_visuals
import openai_runtime

IMAGES_ENDPOINT = "https://api.openai.com/v1/images/generations"
DEFAULT_IMAGE_MODEL = "gpt-image-1-mini"
DEFAULT_IMAGE_QUALITY = "low"
DEFAULT_IMAGE_SIZE = "1024x1024"
MAX_RESPONSE_BYTES = 12_000_000

FUNCTION_SUBJECTS = {
    "pattern_interrupt": "extreme close-up of a fingerstick blood drop on a sterile fingertip",
    "absurd_contrast": "tiny blood collection tube next to a stack of thick medical binders",
    "personal_consequence": "anonymous adult checking a biomarker app beside a clinic chair",
    "scale_or_intensify": "microliter pipette dispensing a drop into a lab cartridge",
    "evidence_receipt": "PCR gel electrophoresis tray under lab light with annotated bands",
    "annotation_or_punch_in": "scientific paper page and highlighter on a clean lab desk",
    "contrast_reset": "Raman laser spectroscopy instrument on a diagnostic lab bench",
    "limitation_overlay": "blurred crowded lab instruments behind one sharp empty sample vial",
    "callback_visual": "side-by-side: optical spectroscopy probe and PCR thermocycler",
    "reaction_or_end_card": "quiet clinical chemistry workstation at end of day",
}

EDITORIAL_STYLE = (
    "Create a restrained editorial-documentary still for a sophisticated science and men's-health "
    "short-form video. Prefer plausible photographed environments, objects, clinical or laboratory "
    "details, documentary composition, real-world texture, natural or practical lighting, and visual "
    "specificity over cartoon metaphors, icons, floating symbols, glossy 3D infographics, or generic "
    "AI concept art. The image is an illustration, never the evidentiary source itself. Do not include "
    "readable claims, fake paper pages, fake chart values, logos, watermarks, identifiable real people, "
    "or fabricated medical results. Keep the composition strong at small picture-in-picture size. "
)


def image_model(env=None):
    env = os.environ if env is None else env
    return str(env.get("OPENAI_IMAGE_MODEL") or DEFAULT_IMAGE_MODEL).strip()


def image_quality(env=None):
    env = os.environ if env is None else env
    return str(env.get("OPENAI_IMAGE_QUALITY") or DEFAULT_IMAGE_QUALITY).strip().casefold()


def prompt_for_slot(slot, draft_topic=""):
    function = str(slot.get("visual_function") or "").strip()
    subject = FUNCTION_SUBJECTS.get(function) or function.replace("_", " ")
    topic_bits = lean_visuals._topic_keywords(draft_topic, limit=4)
    topic_hint = ", ".join(topic_bits) if topic_bits else "biomedical diagnostics"
    return (
        f"Photoreal documentary still for a men's-health science Reel inset. "
        f"Subject: {subject}. Context cues: {topic_hint}. "
        f"Clinical / lab atmosphere, natural light, no logos, no readable brand "
        f"names, no identifiable real person's face, no fabricated chart numbers, "
        f"no text overlays, no watermarks. Square composition with clean negative "
        f"space suitable for a corner picture-in-picture."
    )


def editorial_prompt(prompt):
    """Apply the canonical visual style without discarding beat-specific intent."""
    prompt = str(prompt or "").strip()
    if not prompt:
        raise ValueError("OpenAI still prompt must not be empty")
    return EDITORIAL_STYLE + "Beat-specific visual direction: " + prompt


def _post_images(body, credential, timeout=120):
    request = urllib.request.Request(
        IMAGES_ENDPOINT,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer " + credential,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("OpenAI images response exceeded byte limit")
        return json.loads(raw)
    except urllib.error.HTTPError as exc:
        body_text = exc.read(4000).decode(errors="replace")
        raise RuntimeError(f"OpenAI images HTTP {exc.code}: {body_text}") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"OpenAI images request failed: {type(exc).__name__}") from None


def generate_still_bytes(prompt, credential=None, model=None, quality=None, size=DEFAULT_IMAGE_SIZE):
    """Return PNG/JPEG bytes for one still. Injectable for tests via monkeypatch."""
    credential = credential or openai_runtime.require_live()
    model = model or image_model()
    quality = quality or image_quality()
    body = {
        "model": model,
        "prompt": editorial_prompt(prompt),
        "n": 1,
        "size": size,
        "quality": quality,
    }
    result = _post_images(body, credential)
    data = result.get("data") or []
    if not data:
        raise RuntimeError("OpenAI images returned no data")
    item = data[0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    url = item.get("url")
    if isinstance(url, str) and url.startswith("https://"):
        req = urllib.request.Request(url, headers={"User-Agent": "BioticaOpenAIStills/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read(8_000_001)
    raise RuntimeError("OpenAI images response missing b64_json and url")


def _sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_openai_stills(root, direction, draft_topic="", live=False, generate=None):
    """Return six visual_result dicts compatible with unreviewed_video_preview.build_plan."""
    generate = generate or generate_still_bytes
    root = Path(root)
    out_dir = root / "generated" / "openai-stills"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    catalog = []
    model = image_model()
    quality = image_quality()
    for index, slot in enumerate(direction["render_slots"]):
        cue = slot["cue_id"]
        prompt = prompt_for_slot(slot, draft_topic)
        if not live:
            rel = f"generated/openai-stills/{cue}-dry.mp4"
            results.append({
                "state": "dry_run",
                "candidate": {
                    "id": f"openai-still-dry:{cue}",
                    "cue_id": cue,
                    "media_source": rel,
                    "provider": "openai",
                    "prompt": prompt,
                    "model": model,
                    "quality": quality,
                },
                "rights_status": "preview_generated",
                "license_basis": "OpenAI-generated still (dry-run placeholder)",
                "credit": "AI-GENERATED STILL (DRY RUN)",
                "visual_type": "illustration",
            })
            continue

        stem = f"{index:02d}-{cue}"
        image_path = out_dir / f"{stem}.png"
        video_path = out_dir / f"{stem}.mp4"
        meta_path = out_dir / f"{stem}.json"
        image_bytes = generate(prompt)
        if not image_bytes:
            raise RuntimeError(f"Empty OpenAI still for cue {cue!r}")
        image_path.write_bytes(image_bytes)
        lean_visuals.still_to_loop_mp4(image_path, video_path)
        rel = str(video_path.relative_to(root))
        candidate = {
            "id": f"openai-still:{cue}:{_sha(video_path)[:12]}",
            "cue_id": cue,
            "media_source": rel,
            "provider": "openai",
            "prompt": prompt,
            "model": model,
            "quality": quality,
        }
        packet = {
            "state": "collected",
            "candidate": candidate,
            "rights_status": "preview_generated",
            "license_basis": f"OpenAI {model} still for private preview",
            "credit": "AI-GENERATED STILL",
            "visual_type": "illustration",
        }
        meta_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
        catalog.append(candidate)
        results.append(packet)
    (out_dir / "catalog.json").write_text(
        json.dumps({
            "schema_version": 1,
            "topic": draft_topic,
            "model": model,
            "quality": quality,
            "candidates": catalog,
        }, indent=2) + "\n",
        encoding="utf-8")
    return results
