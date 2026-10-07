"""Pipeline A: editorial optimization and narration package for Satoshi.

This pipeline deliberately stops before avatar/video production. It normalizes the
canonical episode request, runs three independent editorial critics, resolves them
through a showrunner, locks the script, directs sentence-level prosody, renders
three narration takes, performs bounded audio QA/selection, and emits an immutable
handoff manifest for the production pipeline.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

RESPONSES_ENDPOINT = "https://api.openai.com/v1/responses"
SPEECH_ENDPOINT = "https://api.openai.com/v1/audio/speech"
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "cedar"
PERSONA_LORE_PATH = Path("studio/characters/satoshi-v1/persona_lore.json")
PERSONA_SCENE_PATH = Path("studio/director/persona_scene_schema.json")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(value):
    if isinstance(value, (dict, list)):
        value = canonical(value).encode("utf-8")
    elif isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _post_json(url, body, key, timeout=240):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read(8_000_000))
    except urllib.error.HTTPError as exc:
        body_text = exc.read(8192).decode("utf-8", errors="replace")
        raise RuntimeError(f"Provider HTTP {exc.code}: {body_text}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeError(f"Provider request failed or outcome unknown: {url}") from exc


def _output_text(result):
    chunks = []
    for item in result.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                chunks.append(content.get("text", ""))
    text = "".join(chunks).strip()
    if not text:
        raise ValueError("Model returned no output text")
    return text


def _parse_json_text(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("{"), text.rfind("}")
        if left < 0 or right <= left:
            raise ValueError("Model output was not JSON")
        return json.loads(text[left:right + 1])


def _json_call(key, model, instructions, payload):
    """Call the editorial model and require a complete JSON object.

    Reasoning models can spend a small output budget before the JSON is finished.
    A truncated object is retried once with a larger budget and lower reasoning effort.
    """
    last_error = None
    for attempt in range(2):
        reminder = ""
        if attempt:
            reminder = " The previous reply was truncated or was not valid JSON. Return one compact JSON object and no markdown."
        result = _post_json(RESPONSES_ENDPOINT, {
            "model": model,
            "store": False,
            "instructions": instructions + reminder,
            "input": json.dumps(payload, ensure_ascii=False),
            "max_output_tokens": 8000 if attempt == 0 else 16000,
            "reasoning": {"effort": "low"},
        }, key)
        status = result.get("status")
        if status and status != "completed":
            reason = (result.get("incomplete_details") or {}).get("reason") or status
            last_error = ValueError(f"OpenAI response not completed: {reason}")
            continue
        try:
            return _parse_json_text(_output_text(result))
        except (ValueError, json.JSONDecodeError) as exc:
            last_error = exc
    raise last_error


def normalize_source(request):
    digest = request.get("conversation_digest") or {}
    mining = request.get("editorial_mining") or {}
    intent = request.get("story_intent") or {}
    messages = digest.get("source_messages") or []
    if not messages:
        raise ValueError("Pipeline A requires conversation_digest.source_messages")
    return {
        "summary": digest.get("summary", ""),
        "source_messages": messages,
        "editorial_mining": mining,
        "story_intent": intent,
        "episode_constraints": {
            "target_seconds": (request.get("production") or {}).get("target_seconds", 60),
            "audience": "informed men's-health audience",
            "persona": "Satoshi",
        },
    }


def source_editor(key, model, normalized):
    return _json_call(key, model,
        "You are a source editor. Normalize the supplied material into factual claims, contradictions, interesting moments, humorous possibilities, evidence needs, uncertainties, and citations. Do not write a script. Preserve uncertainty and never invent sources. Return only JSON.",
        normalized)


def editorial_agent(key, model, role, source_packet):
    prompts = {
        "story_editor": "You are the Story Editor. Find the single most compelling story, hook, escalation, evidence sequence and payoff. Be aggressive about narrative value. Preserve provocative implications and memorable lines when defensible. Do not invent facts. Return JSON with central_angle, hook, story_arc, best_evidence, payoff, cut.",
        "scientific_skeptic": "You are a factual red-team guardrail, not a co-author and not a regulator. Identify only claims that are materially false, causally unsupported, or misleading enough to require correction. Prefer one precise boundary sentence over repeated caveats. Do not add regulatory language unless regulation is itself the subject. Do not dilute a provocative but defensible thesis merely because it is speculative. Return JSON with fatal_errors, minimal_required_corrections, strongest_objection, claims_supported, claims_unsupported, stronger_narrower_claims. Keep minimal_required_corrections sparse.",
        "voice_editor": "You are the Satoshi Voice Editor. Improve spoken-language compression, analogies, dry humor, memorable phrasing and rhetorical turns. Persona: smart investor explaining something surprising to an equally smart friend; curious, amused, skeptical, confident; never announcer/corporate/breathless. Protect the central provocative idea from disclaimer creep. Do not alter facts. Return JSON with stronger_phrasing, jokes, analogies, lines_to_keep, lines_to_kill, voice_notes.",
    }
    return _json_call(key, model, prompts[role], source_packet)


def run_editorial_room(key, model, source_packet):
    roles = ["story_editor", "scientific_skeptic", "voice_editor"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {role: pool.submit(editorial_agent, key, model, role, source_packet) for role in roles}
        return {role: futures[role].result() for role in roles}


def showrunner(key, model, source_packet, room):
    lore = json.loads(PERSONA_LORE_PATH.read_text()) if PERSONA_LORE_PATH.exists() else {}
    scene_contract = json.loads(PERSONA_SCENE_PATH.read_text()) if PERSONA_SCENE_PATH.exists() else {}
    payload = {"source_packet": source_packet, "editorial_room": room,
               "persona_lore": lore, "persona_scene_contract": scene_contract}
    out = _json_call(key, model,
        "You are the final Satoshi showrunner. The Story Editor owns narrative center of gravity; the Scientific Skeptic is only a factual veto/constraint layer. Optimize tension -> evidence -> complication -> insight -> payoff. "
        "Satoshi is a recurring fictional character with accumulated lore, not a generic narrator. Every normal episode MUST begin with a short topic-linked fictional autobiographical cold open that reveals something about Satoshi's past, includes one oddly specific technical/operational detail, and pivots directly into the real topic. Prefer an existing compatible lore entry; invent at most one new compatible lore detail. Fictional lore is never evidence. "
        "Also produce one coherent persona_scene describing environment, wardrobe, props, lighting, framing, why the setting fits, and speaking_segments. The environment must be topic-relevant or lore-relevant; do not default to a suit or neutral studio. "
        "The script array must contain at least 10 spoken sentences and about 120 to 160 words. The first 1-2 sentences should normally be the PERSONA_HOOK/PERSONA_PIVOT. Mark each sentence function. "
        "For persona_scene.speaking_segments, reference exact sentence_ids that Satoshi should visibly speak on camera. Prefer 3-5 visible appearances totaling roughly 8-15 seconds, but keep each individual speaking shot compact, usually 3-6 seconds. Focus on persona hook, joke/callback, correction, and/or thesis. Evidence-heavy sentences should usually be off-camera over graphics/B-roll. "
        "Direct Satoshi as a person caught doing something, never as a generic standing presenter. Default to medium-close or waist-up framing. Give him one motivated posture or tiny action appropriate to the world: seated at a machine, leaning on a workbench, looking up from a paper or monitor, inspecting an object, or turning into the line. Avoid full-body standing shots, broad gestures and long talking-head holds. "
        "Return JSON with title, thesis, script (array of sentence_id, text, function, claim_status, citations), persona_scene, closing_payoff, estimated_seconds, visual_intents. Do not include prose outside JSON.",
        payload)
    script = out.get("script")
    if not isinstance(script, list) or not script:
        raise ValueError("Showrunner returned no script")
    for i, sentence in enumerate(script, 1):
        if not str(sentence.get("text") or "").strip():
            raise ValueError("Showrunner emitted empty sentence")
        sentence["sentence_id"] = f"s{i:02d}"
    scene = out.get("persona_scene")
    if not isinstance(scene, dict):
        raise ValueError("Showrunner returned no persona_scene")
    required = ["scene_id", "persona_lore_id", "environment", "wardrobe",
                "persona_hook", "pivot_line", "why_this_setting_fits", "speaking_segments"]
    if any(not scene.get(k) for k in required):
        raise ValueError("Showrunner persona_scene is incomplete")
    valid_ids = {row["sentence_id"] for row in script}
    for segment in scene.get("speaking_segments") or []:
        ids = segment.get("sentence_ids") or []
        if not ids or any(sid not in valid_ids for sid in ids):
            raise ValueError("persona_scene speaking segment references invalid sentence IDs")
    return out


def prosody_director(key, model, locked_script):
    out = _json_call(key, model,
        "You are the Satoshi prosody director. The script words are immutable. For every sentence_id, return performance direction only: emotion, pace multiplier, energy 0-1, emphasis words, pause_before_ms, pause_after_ms, skepticism 0-1, amusement 0-1, and a concise direction. Vary rhythm meaningfully: hooks can be quicker, evidence slower/flatter, objections firm, jokes underplayed, synthesis deliberate, payoff preceded by a pause. Return JSON with global_direction and sentences. NEVER rewrite any script text.",
        locked_script)
    items = out.get("sentences")
    ids = [s["sentence_id"] for s in locked_script["script"]]
    if not isinstance(items, list) or [s.get("sentence_id") for s in items] != ids:
        raise ValueError("Prosody score must cover every locked sentence in order")
    return out


def performance_prompt(locked_script, prosody, variant):
    profiles = {
        "a": "Dry and intellectual. Lower energy, restrained humor, deliberate pauses.",
        "b": "Curious and incredulous. Quicker opening, controlled variation, dry disbelief.",
        "c": "Intimate and conversational. Softer energy, meaningful pauses, relaxed payoff.",
    }
    direction = ""
    if isinstance(prosody, dict):
        direction = str(prosody.get("global_direction") or "").strip()
    # Speech input plus instructions must stay under the provider's 2000-token cap.
    return (
        "Male editorial narrator. Natural American English. Smart, dry, skeptical, slightly amused. "
        "Never announcer-like, commercial, motivational, or synthetic. Speak every word exactly. "
        + profiles[variant]
        + ((" " + direction) if direction else "")
    )[:900]


def render_take(text, instructions, target, key, model, voice):
    body = {"model": model, "voice": voice, "input": text, "instructions": instructions,
            "response_format": "wav"}
    req = urllib.request.Request(
        SPEECH_ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=240) as response:
            audio = response.read(50_000_000)
    except urllib.error.HTTPError as exc:
        detail = exc.read(400).decode("utf-8", "replace")
        raise RuntimeError(f"Narration generation failed: HTTP {exc.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("Narration generation failed or outcome unknown") from exc
    if not audio:
        raise ValueError("Narration provider returned empty audio")
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(audio)
    return target


def duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)
    ], check=True, capture_output=True, text=True, timeout=60)
    return float(result.stdout.strip())


def audio_qa(takes, target_seconds):
    rows = []
    for name, path in takes.items():
        seconds = duration(path)
        size = Path(path).stat().st_size
        valid = seconds > 0.5 and size > 1024
        rows.append({"take": name, "file": str(path), "duration_seconds": round(seconds, 3),
                     "bytes": size, "valid": valid,
                     "duration_error": abs(seconds - float(target_seconds))})
    valid_rows = [r for r in rows if r["valid"]]
    if not valid_rows:
        raise RuntimeError("No valid narration take")
    winner = min(valid_rows, key=lambda r: r["duration_error"])
    return {"selection_mode": "mechanical_duration_qa", "selected": winner["take"],
            "takes": rows, "note": "Prosody quality still requires human or audio-model review."}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True)
    parser.add_argument("--output", default="outputs/satoshi-editorial")
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args(argv)

    request = json.loads(Path(args.request).read_text(encoding="utf-8"))
    normalized = normalize_source(request)
    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    write_json(root / "normalized_source.json", normalized)

    if not args.live:
        write_json(root / "manifest.json", {"schema_version": 1, "status": "dry_run", "request_sha256": sha(request)})
        return 0

    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY required")
    model = os.environ.get("SATOSHI_EDITORIAL_MODEL", DEFAULT_MODEL)
    tts_model = os.environ.get("SATOSHI_EDITORIAL_TTS_MODEL", DEFAULT_TTS_MODEL)
    voice = os.environ.get("SATOSHI_EDITORIAL_TTS_VOICE", DEFAULT_TTS_VOICE)

    packet = source_editor(key, model, normalized)
    write_json(root / "source_packet.json", packet)
    room = run_editorial_room(key, model, packet)
    for role, value in room.items():
        write_json(root / "editorial_room" / f"{role}.json", value)

    locked = showrunner(key, model, packet, room)
    write_json(root / "canonical_script.json", locked)
    prosody = prosody_director(key, model, locked)
    write_json(root / "performance_score.json", prosody)

    text = " ".join(s["text"].strip() for s in locked["script"])
    takes = {}
    for variant in ("a", "b", "c"):
        target = root / "narration" / f"take-{variant}.wav"
        render_take(text, performance_prompt(locked, prosody, variant), target, key, tts_model, voice)
        takes[variant] = target

    target_seconds = normalized["episode_constraints"]["target_seconds"]
    evaluation = audio_qa(takes, target_seconds)
    write_json(root / "audio_evaluation.json", evaluation)
    selected = takes[evaluation["selected"]]
    selected_copy = root / "narration" / "selected.wav"
    selected_copy.write_bytes(Path(selected).read_bytes())

    visual_intents = locked.get("visual_intents") or []
    write_json(root / "visual_intents.json", visual_intents)
    manifest = {
        "schema_version": 1,
        "status": "editorially_approved_with_mechanical_audio_qa",
        "request_sha256": sha(request),
        "script_sha256": sha(locked),
        "performance_sha256": sha(prosody),
        "audio_sha256": hashlib.sha256(selected_copy.read_bytes()).hexdigest(),
        "selected_audio": "narration/selected.wav",
        "canonical_script": "canonical_script.json",
        "performance_score": "performance_score.json",
        "visual_intents": "visual_intents.json",
        "tts_provider": "openai",
        "tts_model": tts_model,
        "tts_voice": voice,
        "audio_selection_mode": evaluation["selection_mode"],
    }
    write_json(root / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
