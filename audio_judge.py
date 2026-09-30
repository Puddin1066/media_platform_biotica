"""Audio-capable judge for Satoshi narration takes.

Uses an audio-input model to compare rendered takes against the immutable script
and prosody score. It may rank/select performances but may never rewrite the
script or performance specification.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

CHAT_ENDPOINT = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-audio-1.5"


def _encode_wav(path):
    data = Path(path).read_bytes()
    if not data:
        raise ValueError(f"Empty audio file: {path}")
    return base64.b64encode(data).decode("ascii")


def _extract_json(text):
    text = str(text or "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("{"), text.rfind("}")
        if left < 0 or right <= left:
            raise ValueError("Audio judge returned non-JSON output")
        return json.loads(text[left:right + 1])


def judge(takes, locked_script, prosody, key, model=None):
    """Compare A/B/C WAV takes and return a bounded editorial performance verdict."""
    model = (model or os.environ.get("SATOSHI_AUDIO_JUDGE_MODEL") or DEFAULT_MODEL).strip()
    required = {"a", "b", "c"}
    if set(takes) != required:
        raise ValueError("Audio judge requires exactly takes a, b, and c")

    packet = {
        "script": locked_script,
        "performance_score": prosody,
        "rubric": [
            "naturalness",
            "prosodic_variation",
            "satoshi_identity",
            "scientific_authority",
            "humor_delivery",
            "payoff",
            "instruction_adherence",
        ],
        "persona": "Dry, intelligent, skeptical, slightly amused; smart investor to smart friend; never announcer-like.",
        "rules": [
            "Judge audio performance only; never rewrite script wording.",
            "Score each rubric dimension 0-10 for every take.",
            "Select exactly one of a, b, or c.",
            "Penalize clipping, robotic cadence, exaggerated acting, monotony, and missed pauses.",
            "Return only JSON with selected, takes, selection_reason, regenerate, weak_ranges.",
        ],
    }
    content = [{
        "type": "text",
        "text": "Compare these three narration takes against this immutable packet:\n" + json.dumps(packet, ensure_ascii=False),
    }]
    for name in ("a", "b", "c"):
        content.append({"type": "text", "text": f"TAKE {name.upper()}:"})
        content.append({
            "type": "input_audio",
            "input_audio": {"data": _encode_wav(takes[name]), "format": "wav"},
        })

    body = {
        "model": model,
        "modalities": ["text"],
        "messages": [{"role": "user", "content": content}],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        CHAT_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read(8_000_000))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError("Audio judge request failed or outcome is unknown") from exc

    choices = result.get("choices") or []
    if not choices:
        raise ValueError("Audio judge returned no choices")
    verdict = _extract_json((choices[0].get("message") or {}).get("content"))
    if verdict.get("selected") not in required:
        raise ValueError("Audio judge selected an invalid take")
    scores = verdict.get("takes")
    if not isinstance(scores, dict) or set(scores) != required:
        raise ValueError("Audio judge must score all three takes")
    verdict["selection_mode"] = "audio_model_comparison"
    verdict["model"] = model
    return verdict
