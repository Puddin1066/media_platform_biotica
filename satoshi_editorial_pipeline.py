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


def _json_call(key, model, instructions, payload):
    result = _post_json(RESPONSES_ENDPOINT, {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 5000,
    }, key)
    text = _output_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("{"), text.rfind("}")
        if left < 0 or right <= left:
            raise ValueError("Model output was not JSON")
        return json.loads(text[left:right + 1])


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
        "story_editor": "You are the Story Editor. Find the single most compelling story, hook, escalation, evidence sequence and payoff. Be aggressive about narrative value but do not invent facts. Return JSON with central_angle, hook, story_arc, best_evidence, payoff, cut.",
        "scientific_skeptic": "You are the Scientific Skeptic. Try to break the story: causal overclaims, mechanism-versus-efficacy confusion, selection effects, missing controls, extrapolation, counterarguments. Prefer stronger narrower claims rather than bland caution. Return JSON with fatal_errors, required_qualifications, strongest_objection, claims_supported, claims_unsupported, stronger_narrower_claims.",
        "voice_editor": "You are the Satoshi Voice Editor. Improve spoken-language compression, analogies, dry humor, memorable phrasing and rhetorical turns. Persona: smart investor explaining something surprising to an equally smart friend; curious, amused, skeptical, confident; never announcer/corporate/breathless. Do not alter facts. Return JSON with stronger_phrasing, jokes, analogies, lines_to_keep, lines_to_kill, voice_notes.",
    }
    return _json_call(key, model, prompts[role], source_packet)


def run_editorial_room(key, model, source_packet):
    roles = ["story_editor", "scientific_skeptic", "voice_editor"]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {role: pool.submit(editorial_agent, key, model, role, source_packet) for role in roles}
        return {role: futures[role].result() for role in roles}


def showrunner(key, model, source_packet, room):
    payload = {"source_packet": source_packet, "editorial_room": room}
    out = _json_call(key, model,
        "You are the final Satoshi showrunner. Resolve the three independent editorial recommendations into one locked spoken script. Optimize tension -> evidence -> complication -> insight -> payoff. Use short spoken sentences, contractions, direct objections, restrained humor. Never weaken scientific accuracy. Return JSON with title, thesis, script (array of sentence_id, text, function, claim_status, citations), closing_payoff, estimated_seconds, visual_intents. Do not include prose outside JSON.",
        payload)
    script = out.get("script")
    if not isinstance(script, list) or not script:
        raise ValueError("Showrunner returned no script")
    for i, sentence in enumerate(script, 1):
        if not str(sentence.get("text") or "").strip():
            raise ValueError("Showrunner emitted empty sentence")
        sentence["sentence_id"] = f"s{i:02d}"
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
        "a": "Dry/intellectual: lower energy, skeptical, restrained humor, deliberate pauses.",
        "b": "Curious/incredulous: quicker opening, more pitch and pace variation, controlled disbelief.",
        "c": "Intimate/conspiratorial: close conversational delivery, softer energy, longer meaningful pauses, strong relaxed payoff.",
    }
    return (
        "Male editorial narrator. Natural American English. Smart, dry, skeptical, slightly amused. "
        "Never announcer-like, commercial, motivational, or synthetic. " + profiles[variant] +
        " Follow this performance score while speaking the script exactly as written: " +
        json.dumps(prosody, ensure_ascii=False)
    )


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
    """Bounded mechanical QA. This intentionally does not pretend to hear aesthetics.

    Until an audio-capable judge model is explicitly configured, selection uses file
    integrity and duration proximity, while preserving every take for human or later
    multimodal review.
    """
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
