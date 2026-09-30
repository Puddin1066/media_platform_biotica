from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import audio_judge
import media_store
import satoshi_editorial_pipeline as base

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def episode_root(episode_id):
    return ROOT / "studio" / "episodes" / episode_id


def artifact_path(episode_id, module, name=None):
    root = episode_root(episode_id) / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root / (name or f"{module}.json")


def load_manifest(episode_id):
    return read_json(episode_root(episode_id) / "episode_manifest.json")


def save_manifest(episode_id, manifest):
    return write_json(episode_root(episode_id) / "episode_manifest.json", manifest)


def mark(manifest, module, status, **extra):
    state = manifest["modules"].setdefault(module, {"version": 0})
    state["status"] = status
    state.update(extra)
    return state


def complete(episode_id, manifest, module, outputs):
    state = manifest["modules"].setdefault(module, {"version": 0})
    state["version"] = int(state.get("version") or 0) + 1
    state["status"] = "needs_review" if module in {"story", "script", "audio_review", "assembly"} else "completed"
    state["outputs"] = outputs
    # downstream artifacts are not deleted; they are marked stale
    registry = read_json(ROOT / "studio" / "modules.json")["modules"]
    dependents = {m["id"]: set(m.get("requires", [])) for m in registry}
    queue = [module]
    seen = set()
    while queue:
        changed = queue.pop(0)
        for child, requires in dependents.items():
            if child in seen or changed not in requires:
                continue
            seen.add(child)
            child_state = manifest["modules"].setdefault(child, {"version": 0})
            if int(child_state.get("version") or 0) > 0:
                child_state["status"] = "stale"
            elif child_state.get("status") == "not_ready":
                child_state["status"] = "ready"
            queue.append(child)
    save_manifest(episode_id, manifest)


def compact_json_call(key, model, instructions, payload, attempts=2):
    last = None
    for attempt in range(attempts):
        try:
            suffix = " Return compact valid JSON only. Keep the response under 2500 tokens." if attempt else ""
            return base._json_call(key, model, instructions + suffix, payload)
        except Exception as exc:
            last = exc
    raise last


def run_source(episode_id, request, key, model):
    normalized = base.normalize_source(request)
    packet = base.source_editor(key, model, normalized)
    p = write_json(artifact_path(episode_id, "source", "source_packet.json"), packet)
    return [str(p.relative_to(ROOT))]


def run_research(episode_id, request, key, model):
    source = read_json(artifact_path(episode_id, "source", "source_packet.json"))
    packet = compact_json_call(
        key, model,
        "You are the research module for Satoshi Studio. Turn the source packet into a claim ledger. Do not invent citations. Separate supported claims, claims requiring external verification, counterarguments, uncertainty, and allowed versus forbidden language. Return JSON with claims, strongest_evidence, counterevidence, open_questions, sources_to_verify.",
        source,
    )
    p = write_json(artifact_path(episode_id, "research", "research_packet.json"), packet)
    return [str(p.relative_to(ROOT))]


def run_story(episode_id, request, key, model):
    source = read_json(artifact_path(episode_id, "source", "source_packet.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    payload = {"source": source, "research": research, "target_seconds": (request.get("production") or {}).get("target_seconds", 60)}
    room = base.run_editorial_room(key, model, source)
    plan = compact_json_call(
        key, model,
        "You are the Satoshi showrunner planning module. Do NOT write the monologue. Resolve the editorial room into one story plan optimized for a short spoken episode. Return JSON with central_question, thesis, hook, audience_objection, escalation, key_receipt, payoff, mens_health_bridge, tone, target_seconds, cuts.",
        {"payload": payload, "editorial_room": room},
    )
    write_json(artifact_path(episode_id, "story", "editorial_room.json"), room)
    p = write_json(artifact_path(episode_id, "story", "story_plan.json"), plan)
    return [str(p.relative_to(ROOT)), str(artifact_path(episode_id, "story", "editorial_room.json").relative_to(ROOT))]


def script_seconds(words):
    return round(words / 2.35, 1)


def run_script(episode_id, request, key, model):
    story = read_json(artifact_path(episode_id, "story", "story_plan.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    target = int(story.get("target_seconds") or (request.get("production") or {}).get("target_seconds", 60))
    max_seconds = max(target + 15, int(target * 1.25))
    max_words = int(max_seconds * 2.35)
    out = compact_json_call(
        key, model,
        f"Write the final locked Satoshi monologue from this story plan and research. Spoken, provocative, scientifically disciplined, dry and concise. Hard maximum {max_words} words. Return JSON with title, thesis, script as an array of objects with text/function/claim_ids, closing_payoff. Do not include prose outside JSON.",
        {"story_plan": story, "research": research},
    )
    sentences = out.get("script") or []
    if not sentences:
        raise ValueError("Script module returned no sentences")
    for i, sentence in enumerate(sentences, 1):
        sentence["sentence_id"] = f"s{i:02d}"
    text = " ".join(str(s.get("text") or "").strip() for s in sentences).strip()
    words = len(text.split())
    estimated = script_seconds(words)
    out["word_count"] = words
    out["target_seconds"] = target
    out["estimated_seconds"] = estimated
    out["duration_gate"] = "pass" if estimated <= max_seconds else "fail"
    json_path = write_json(artifact_path(episode_id, "script", "canonical_script.json"), out)
    txt_path = artifact_path(episode_id, "script", "script.txt")
    txt_path.write_text(text + "\n", encoding="utf-8")
    if estimated > max_seconds:
        raise ValueError(f"Script duration gate failed: estimated {estimated}s, hard max {max_seconds}s")
    return [str(json_path.relative_to(ROOT)), str(txt_path.relative_to(ROOT))]


def run_prosody(episode_id, request, key, model):
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = compact_json_call(
        key, model,
        "The script text is immutable. For every sentence_id return only performance direction: sentence_id, emotion, pace, energy 0-1, emphasis, pause_before_ms, pause_after_ms, skepticism 0-1, amusement 0-1, direction. Return JSON with global_direction and sentences. Never repeat or rewrite sentence text.",
        {"sentence_ids": [{"sentence_id": s["sentence_id"], "function": s.get("function", "")} for s in script["script"]]},
    )
    ids = [s["sentence_id"] for s in script["script"]]
    got = [s.get("sentence_id") for s in prosody.get("sentences", [])]
    if ids != got:
        raise ValueError("Prosody output does not cover the locked script exactly")
    p = write_json(artifact_path(episode_id, "prosody", "performance_score.json"), prosody)
    return [str(p.relative_to(ROOT))]


def run_voice(episode_id, request, key, model):
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = read_json(artifact_path(episode_id, "prosody", "performance_score.json"))
    text = " ".join(s["text"] for s in script["script"])
    outdir = ROOT / "outputs" / "studio" / episode_id / "voice"
    outdir.mkdir(parents=True, exist_ok=True)
    tts_model = os.environ.get("SATOSHI_EDITORIAL_TTS_MODEL", base.DEFAULT_TTS_MODEL)
    voice = os.environ.get("SATOSHI_EDITORIAL_TTS_VOICE", base.DEFAULT_TTS_VOICE)
    variants = {
        "a":"Dry and intellectual. Restrained humor, deliberate pauses, low theatricality.",
        "b":"Curious and incredulous. Quicker opening, controlled variation, dry disbelief.",
        "c":"Intimate and conversational. Softer energy, meaningful pauses, relaxed payoff."
    }
    refs = {}
    for name, direction in variants.items():
        target = outdir / f"take-{name}.wav"
        base.render_take(text, "Natural American male editorial narrator. Smart, skeptical, slightly amused. Never announcer-like. " + direction, target, key, tts_model, voice)
        stored = media_store.persist(target, f"satoshi-studio/{episode_id}/voice/take-{name}.wav")
        refs[name] = stored
    p = write_json(artifact_path(episode_id, "voice", "voice_manifest.json"), {"takes": refs, "model": tts_model, "voice": voice})
    return [str(p.relative_to(ROOT))]


def run_audio_review(episode_id, request, key, model):
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = read_json(artifact_path(episode_id, "prosody", "performance_score.json"))
    voice_manifest = read_json(artifact_path(episode_id, "voice", "voice_manifest.json"))
    outdir = ROOT / "outputs" / "studio" / episode_id / "audio_review"
    outdir.mkdir(parents=True, exist_ok=True)
    local = {}
    for name, ref in voice_manifest["takes"].items():
        path = outdir / f"take-{name}.wav"
        media_store.fetch(ref["key"], path)
        local[name] = path
    verdict = audio_judge.judge(local, script, prosody, key)
    selected = verdict["selected"]
    selected_ref = voice_manifest["takes"][selected]
    verdict["selected_audio"] = selected_ref
    p = write_json(artifact_path(episode_id, "audio_review", "audio_evaluation.json"), verdict)
    return [str(p.relative_to(ROOT))]


def run_visual_plan(episode_id, request, key, model):
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    plan = compact_json_call(
        key, model,
        "Create a shot plan for this immutable script. Do not change narration. Return JSON with shots; each shot has shot_id, sentence_ids, type, intent, source_priority, label_requirements. Prefer host/evidence/generated illustration/chart/typography/dynamic_broll/metaphor/joke_visual/callback as appropriate.",
        {"script": script, "research": research},
    )
    p = write_json(artifact_path(episode_id, "visual_plan", "visual_plan.json"), plan)
    return [str(p.relative_to(ROOT))]


def run_host(episode_id, request, key, model):
    """Record an existing R2 plate as this episode's host.

    The Studio host module does not render or upload a new video. It selects one
    object already stored under satoshi/plates/ and writes that key into the
    episode manifest.
    """
    del key, model
    host = dict((request or {}).get("host") or {})
    explicit = str(host.get("r2_key") or (request or {}).get("plate_r2_key") or "").strip()
    chosen = media_store.resolve_plate(episode_id, explicit or None)
    record = {
        "schema_version": 1,
        "generated": False,
        "source": chosen["source"],
        "plate": {"key": chosen["key"], "bytes": chosen.get("bytes")},
        "note": "Reused an available plate. No new host video was generated.",
    }
    path = write_json(artifact_path(episode_id, "host", "host_manifest.json"), record)
    return [str(path.relative_to(ROOT))]


def run_adapter(episode_id, module):
    p = write_json(artifact_path(episode_id, module, f"{module}_adapter.json"), {
        "status": "adapter_ready",
        "module": module,
        "note": "This module currently hands off to the existing production runtime; it is isolated in the Studio graph but not yet decomposed internally."
    })
    return [str(p.relative_to(ROOT))]


RUNNERS = {
    "source": run_source,
    "research": run_research,
    "story": run_story,
    "script": run_script,
    "prosody": run_prosody,
    "voice": run_voice,
    "audio_review": run_audio_review,
    "visual_plan": run_visual_plan,
    "host": run_host,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--module", required=True)
    args = ap.parse_args()
    episode_id, module = args.episode, args.module
    manifest = load_manifest(episode_id)
    registry = {m["id"]: m for m in read_json(ROOT / "studio" / "modules.json")["modules"]}
    if module not in registry:
        raise ValueError(f"Unknown module: {module}")
    for dep in registry[module].get("requires", []):
        status = manifest["modules"].get(dep, {}).get("status")
        if status not in {"completed", "approved", "needs_review"}:
            raise ValueError(f"{module} requires {dep}; current status={status}")
    mark(manifest, module, "running")
    save_manifest(episode_id, manifest)
    request = read_json(ROOT / manifest["request_path"])
    key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("SATOSHI_EDITORIAL_MODEL", base.DEFAULT_MODEL)
    try:
        if module in RUNNERS:
            outputs = RUNNERS[module](episode_id, request, key, model)
        else:
            outputs = run_adapter(episode_id, module)
        complete(episode_id, manifest, module, outputs)
    except Exception as exc:
        mark(manifest, module, "failed", error=str(exc))
        save_manifest(episode_id, manifest)
        raise
    print(json.dumps({"episode_id": episode_id, "module": module, "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
