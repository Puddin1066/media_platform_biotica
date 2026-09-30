"""Pipeline A entrypoint with real audio-model take selection.

Reuses the editorial/story/prosody/TTS helpers from satoshi_editorial_pipeline,
but replaces duration-based selection with an audio-capable comparative judge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import audio_judge
import satoshi_editorial_pipeline as base


def mechanical_validate(takes):
    rows = []
    for name, path in takes.items():
        seconds = base.duration(path)
        size = Path(path).stat().st_size
        valid = seconds > 0.5 and size > 1024
        rows.append({
            "take": name,
            "file": str(path),
            "duration_seconds": round(seconds, 3),
            "bytes": size,
            "valid": valid,
        })
    if not all(row["valid"] for row in rows):
        raise RuntimeError("One or more narration takes failed mechanical audio validation")
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", default="outputs/satoshi-editorial")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    normalized = base.normalize_source(request)
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    base.write_json(root / "normalized_source.json", normalized)

    if not args.live:
        base.write_json(root / "manifest.json", {
            "schema_version": 1,
            "status": "dry_run",
            "request_sha256": base.sha(request),
            "audio_judge": "gpt-audio-1.5",
        })
        return 0

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY required")
    model = os.environ.get("SATOSHI_EDITORIAL_MODEL", base.DEFAULT_MODEL)
    tts_model = os.environ.get("SATOSHI_EDITORIAL_TTS_MODEL", base.DEFAULT_TTS_MODEL)
    voice = os.environ.get("SATOSHI_EDITORIAL_TTS_VOICE", base.DEFAULT_TTS_VOICE)
    judge_model = os.environ.get("SATOSHI_AUDIO_JUDGE_MODEL", audio_judge.DEFAULT_MODEL)

    packet = base.source_editor(key, model, normalized)
    base.write_json(root / "source_packet.json", packet)

    room = base.run_editorial_room(key, model, packet)
    for role, value in room.items():
        base.write_json(root / "editorial_room" / f"{role}.json", value)

    locked = base.showrunner(key, model, packet, room)
    base.write_json(root / "canonical_script.json", locked)
    prosody = base.prosody_director(key, model, locked)
    base.write_json(root / "performance_score.json", prosody)

    text = " ".join(s["text"].strip() for s in locked["script"])
    takes = {}
    for variant in ("a", "b", "c"):
        target = root / "narration" / f"take-{variant}.wav"
        base.render_take(
            text,
            base.performance_prompt(locked, prosody, variant),
            target,
            key,
            tts_model,
            voice,
        )
        takes[variant] = target

    mechanical = mechanical_validate(takes)
    verdict = audio_judge.judge(takes, locked, prosody, key, model=judge_model)
    evaluation = {
        "selection_mode": verdict["selection_mode"],
        "model": verdict["model"],
        "selected": verdict["selected"],
        "mechanical_validation": mechanical,
        "takes": verdict["takes"],
        "selection_reason": verdict.get("selection_reason", ""),
        "regenerate": bool(verdict.get("regenerate", False)),
        "weak_ranges": verdict.get("weak_ranges") or [],
    }
    base.write_json(root / "audio_evaluation.json", evaluation)

    selected = takes[evaluation["selected"]]
    selected_copy = root / "narration" / "selected.wav"
    selected_copy.write_bytes(Path(selected).read_bytes())

    visual_intents = locked.get("visual_intents") or []
    base.write_json(root / "visual_intents.json", visual_intents)
    manifest = {
        "schema_version": 1,
        "status": "editorially_approved_with_audio_model_judge",
        "request_sha256": base.sha(request),
        "script_sha256": base.sha(locked),
        "performance_sha256": base.sha(prosody),
        "audio_sha256": hashlib.sha256(selected_copy.read_bytes()).hexdigest(),
        "selected_audio": "narration/selected.wav",
        "canonical_script": "canonical_script.json",
        "performance_score": "performance_score.json",
        "visual_intents": "visual_intents.json",
        "tts_provider": "openai",
        "tts_model": tts_model,
        "tts_voice": voice,
        "audio_selection_mode": evaluation["selection_mode"],
        "audio_judge_model": judge_model,
        "audio_judge_selected_take": evaluation["selected"],
        "audio_judge_requests_regeneration": evaluation["regenerate"],
    }
    base.write_json(root / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
