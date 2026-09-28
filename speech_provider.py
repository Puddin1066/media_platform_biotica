"""Canonical narration provider for Satoshi shorts.

ElevenLabs is preferred when configured because it returns speech plus timing in
one response. Runway remains the compatibility fallback. The exact generated
beat files become the audio source used for both host performance and final mix.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from speech_timing import BEATS

ELEVENLABS_ENDPOINT = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"


def selected_provider():
    configured = os.environ.get("SATOSHI_SPEECH_PROVIDER", "auto").strip().lower()
    if configured not in {"auto", "elevenlabs", "runway"}:
        raise ValueError("SATOSHI_SPEECH_PROVIDER must be auto, elevenlabs, or runway")
    if configured == "auto":
        if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
            return "elevenlabs"
        return "runway"
    return configured


def _word_timings(alignment):
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    if not (len(chars) == len(starts) == len(ends)):
        raise ValueError("ElevenLabs alignment arrays differ in length")
    words, token, token_start, token_end = [], [], None, None
    for ch, start, end in zip(chars, starts, ends):
        if str(ch).isspace():
            if token:
                words.append({"text": "".join(token), "start": token_start, "end": token_end})
                token, token_start, token_end = [], None, None
            continue
        if token_start is None:
            token_start = start
        token.append(ch)
        token_end = end
    if token:
        words.append({"text": "".join(token), "start": token_start, "end": token_end})
    return words


def _elevenlabs(text, voice_id, key, model_id):
    body = {
        "text": text,
        "model_id": model_id,
        "apply_text_normalization": "auto",
        "seed": 1066,
    }
    req = urllib.request.Request(
        ELEVENLABS_ENDPOINT.format(voice_id=voice_id),
        data=json.dumps(body).encode("utf-8"),
        headers={"xi-api-key": key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            result = json.loads(response.read(20_000_000))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError("ElevenLabs speech request failed or outcome is unknown") from exc
    audio = result.get("audio_base64")
    alignment = result.get("normalized_alignment") or result.get("alignment")
    if not isinstance(audio, str) or not isinstance(alignment, dict):
        raise ValueError("ElevenLabs response missing audio or alignment")
    return base64.b64decode(audio), alignment


def generate_episode_audio(root, board, live=False):
    provider = selected_provider()
    if provider != "elevenlabs":
        return {"provider": provider, "status": "delegated_to_runway"}
    if not live:
        return {"provider": provider, "status": "dry_run"}

    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    model_id = os.environ.get("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2").strip()
    if not key or not voice_id:
        raise ValueError("ElevenLabs selected but ELEVENLABS_API_KEY/ELEVENLABS_VOICE_ID missing")

    root = Path(root)
    audio_dir = root / "audio"
    align_dir = root / "generated" / "alignment"
    audio_dir.mkdir(parents=True, exist_ok=True)
    align_dir.mkdir(parents=True, exist_ok=True)
    cues = {c["cue_id"]: c for c in board.get("cues", [])}
    output = {}
    for beat in BEATS:
        target = audio_dir / f"{beat}.mp3"
        timing = align_dir / f"{beat}.json"
        text = str(cues[beat]["spoken_text"]).strip()
        if target.is_file() and timing.is_file():
            output[beat] = {"status": "audio_ready", "file": str(target), "alignment": str(timing)}
            continue
        audio_bytes, alignment = _elevenlabs(text, voice_id, key, model_id)
        part = target.with_suffix(".part.mp3")
        part.write_bytes(audio_bytes)
        part.replace(target)
        manifest = {
            "schema_version": 1,
            "provider": "elevenlabs",
            "model_id": model_id,
            "voice_id": voice_id,
            "requested_text": text,
            "normalized_text": "".join(alignment.get("characters") or []),
            "characters": alignment,
            "words": _word_timings(alignment),
        }
        timing.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        output[beat] = {"status": "audio_ready", "file": str(target), "alignment": str(timing)}
    return {"provider": "elevenlabs", "status": "audio_ready", "beats": output}
