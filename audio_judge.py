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

    rubric = {
        "script": locked_script,
        "performance_score": prosody,
        "rubric": {
            "naturalness": "Does this sound like a real person speaking rather than synthesized narration?",
            "prosodic_variation": "Are pace, pitch, emphasis, and pauses varied meaningfully rather than mechanically?",
            "satoshi_identity": "Dry, intelligent, skeptical, slightly amused; smart-investor-to-smart-friend, never announcer-like.",
            "scientific_authority": "Evidence and corrective claims should sound calm, precise, and credible.",
            "humor_delivery": "Jokes should be underplayed rather than sold or shouted.",
            "payoff": "The closing synthesis/button should feel deliberate and memorable.",
            "instruction_adherence": "Does the performance follow the supplied sentence-level prosody directions?",
        },
        "rules": [
            "Judge the audio performance only; do not rewrite or suggest alternate script wording.",
            "Score each criterion from 0 to 10 for each take.",
            "Select exactly one of a, b, or c.",
            "Penalize clipping, robotic cadence, exaggerated acting, monotony, or missed pauses.",
            "Return only JSON.",
        ],
        "output_schema": {
            "selected": "a|b|c",
            "takes": {
                "a": {"naturalness": 0, "prosodic_variation": 0, "satoshi_identity": 0, "scientific_authority": 0, "humor_delivery": 0, "payoff": 0, "instruction_adherence": 0, "overall": 0, "notes": ""},
                "b": {},
                "c": {},
            },
            "selection_reason": "",
            "regenerate": False,
            "weak_ranges": [],
        },
    }

    content = [{
        "type": "text",
        "text": "You are the Satoshi narration audio judge. Compare the three labeled audio takes using this immutable editorial packet:\n" + json.dumps(rubric, ensure_ascii=False),
    }]
    for name in ("a", "b", "c"):
        content.append({"type": "text", "text": f"TAKE {name.upper()} follows:"})
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
