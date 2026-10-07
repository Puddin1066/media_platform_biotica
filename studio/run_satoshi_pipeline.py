"""Canonical end-to-end Satoshi production orchestrator.

One request -> research -> evidence graph -> story -> script -> prosody -> voice
-> alignment -> visual plan -> assets -> synced host -> Remotion assembly -> optional publish.

The orchestrator is resumable and fail-closed. Completed modules are reused when
their persisted artifacts remain current. It never substitutes a legacy host or
graphics mode after a failed stage.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = [
    "source",
    "research",
    "story",
    "script",
    "prosody",
    "voice",
    "audio_review",
    "alignment",
    "visual_plan",
    "director_500",
    "assets",
    "host",
    "assembly",
]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def slug(text):
    value = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return (value[:72] or "satoshi-episode")


def normalize_request(raw):
    topic = str(raw.get("topic") or raw.get("prompt") or "").strip()
    if not topic:
        digest = raw.get("conversation_digest") or {}
        topic = str(digest.get("summary") or "").strip()
    if not topic:
        raise ValueError("Canonical Satoshi request requires topic/prompt/conversation_digest.summary")

    production = dict(raw.get("production") or {})
    production.setdefault("target_seconds", 60)
    production.setdefault("hard_max_seconds", 90)
    production.setdefault("hard_min_seconds", 30)
    production.setdefault("max_overlay_images", 18)
    production.setdefault("max_runway_credits", 650)
    production.setdefault("sound_design", True)
    production.setdefault("publish_instagram", False)

    persona_scene = dict(raw.get("persona_scene") or {})
    if not persona_scene:
        persona_scene = {
            "environment": str(raw.get("environment") or "topic-relevant cinematic environment"),
            "wardrobe": "rumpled dark overshirt over charcoal T-shirt; no suit, no tie",
            "props": [],
            "lighting": "motivated practical light with grounded documentary realism",
            "camera_framing": "waist-up, seated or task-oriented, natural adult proportions",
            "camera_motion": "stable or subtle documentary movement",
            "speaking_segments": [],
        }

    request = {
        "schema_version": 2,
        "format": {"id": "satoshi_reel"},
        "trigger_phrase": raw.get("trigger_phrase") or "Make a Satoshi out of this",
        "topic": topic,
        "conversation_digest": raw.get("conversation_digest") or {
            "summary": topic,
            "source_messages": [{"id": "topic", "speaker": "user", "text": topic}],
        },
        "persona_lore": raw.get("persona_lore") or [],
        "persona_scene": persona_scene,
        "seed_sources": raw.get("seed_sources") or [],
        "required_publications": raw.get("required_publications") or [],
        "production": production,
        "host": {
            "mode": "scene_image_act_two",
            "performance_scope": "persona_segments",
            "performance_max_seconds": 6.5,
            **dict(raw.get("host") or {}),
        },
        "editorial": {
            "fallback_policy": "fail_closed",
            "evidence_visual_policy": "publication_or_visual_not_naked_text",
            "citation_policy": "structured_source_graph",
            **dict(raw.get("editorial") or {}),
        },
    }
    return request


def _canonical_input_view(request):
    value = json.loads(json.dumps(request))
    scene = value.get("persona_scene") or {}
    scene["speaking_segments"] = []
    value["persona_scene"] = scene
    return value


def init_episode(input_path, episode):
    raw = read(input_path)
    request = normalize_request(raw)
    root = ROOT / "studio" / "episodes" / episode
    request_path = root / "request.json"
    manifest_path = root / "episode_manifest.json"
    registry = read(ROOT / "studio" / "modules.json")["modules"]

    if manifest_path.exists():
        existing = read(request_path)
        if _canonical_input_view(existing) != _canonical_input_view(request):
            raise ValueError(
                "Episode already exists with different canonical input; use a new episode ID "
                "so stale paid assets can never be silently reused."
            )
        return root

    modules = {}
    for index, row in enumerate(registry):
        modules[row["id"]] = {"status": "ready" if index == 0 else "not_ready", "version": 0}
    manifest = {
        "schema_version": 2,
        "episode_id": episode,
        "title": raw.get("title") or topic_title(request["topic"]),
        "status": "in_progress",
        "request_path": str(request_path.relative_to(ROOT)),
        "modules": modules,
        "publish": {"manual_approval_required": True, "allowed": False},
        "pipeline": {
            "id": "canonical_satoshi_holistic_v2_tetris_host",
            "fallback_policy": "fail_closed",
            "reuse_completed_modules": True,
        },
    }
    write(request_path, request)
    write(manifest_path, manifest)
    return root


def topic_title(topic):
    text = " ".join(str(topic).split())
    return text[:110] if text else "Satoshi Episode"


def module_status(episode, module):
    manifest = read(ROOT / "studio" / "episodes" / episode / "episode_manifest.json")
    return (manifest.get("modules") or {}).get(module, {}).get("status", "not_ready")


def run_module(episode, module):
    status = module_status(episode, module)
    if status in {"completed", "approved", "needs_review"}:
        print(f"REUSE_MODULE {module} status={status}", flush=True)
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    subprocess.run(
        ["python", "studio/module_runner.py", "--episode", episode, "--module", module],
        cwd=ROOT, env=env, check=True,
    )


def ensure_persona_segments(episode):
    """Derive short visible Satoshi windows from measured narration timing.

    Choose a small set of 3–6.5 second sentence groups spanning the opening,
    middle turn and closing payoff. This keeps performance generation short and
    reusable without requiring hand-authored segment IDs per episode.
    """
    root = ROOT / "studio" / "episodes" / episode
    request_path = root / "request.json"
    request = read(request_path)
    scene = dict(request.get("persona_scene") or {})
    if scene.get("speaking_segments"):
        return

    artifacts = root / "artifacts"
    timing = read(artifacts / "narration_alignment.json")
    script = read(artifacts / "canonical_script.json")
    rows = timing.get("sentences") or []
    if not rows:
        raise RuntimeError("Cannot derive persona segments without narration alignment")

    by_id = {row["sentence_id"]: row for row in rows}
    ordered = [s["sentence_id"] for s in script.get("script", []) if s.get("sentence_id") in by_id]
    if not ordered:
        raise RuntimeError("No aligned script sentences available for persona segmentation")

    # Build consecutive candidate groups bounded by the qualified Act Two window.
    candidates = []
    for i in range(len(ordered)):
        start = by_id[ordered[i]]["startMs"]
        ids = []
        for j in range(i, len(ordered)):
            ids.append(ordered[j])
            end = by_id[ordered[j]]["endMs"]
            duration = end - start
            if 3000 <= duration <= 6500:
                candidates.append((i, j, duration, list(ids)))
            if duration > 6500:
                break
    if not candidates:
        raise RuntimeError("No 3–6.5 second sentence windows fit the qualified Satoshi host range")

    targets = [0, max(0, len(ordered)//2), len(ordered)-1]
    chosen = []
    used = set()
    for target in targets:
        ranked = sorted(candidates, key=lambda x: (abs(((x[0]+x[1])/2)-target), abs(x[2]-4500)))
        for cand in ranked:
            ids = set(cand[3])
            if ids.isdisjoint(used):
                chosen.append(cand)
                used |= ids
                break

    chosen.sort(key=lambda x: x[0])
    segments = []
    for idx, (_, _, _, ids) in enumerate(chosen, 1):
        segments.append({
            "segment_id": f"persona-{idx:02d}",
            "sentence_ids": ids,
            "role": "SATOSHI_SPEAKING",
            "expression_intensity": 2,
        })
    if not segments:
        raise RuntimeError("Persona segment selection produced no valid speaking windows")
    scene["speaking_segments"] = segments
    request["persona_scene"] = scene
    write(request_path, request)
    print("PERSONA_SEGMENTS", json.dumps(segments), flush=True)


def approve_for_publish(episode):
    path = ROOT / "studio" / "episodes" / episode / "episode_manifest.json"
    manifest = read(path)
    assembly = manifest["modules"].get("assembly") or {}
    if assembly.get("status") != "needs_review":
        raise RuntimeError("Assembly must exist in needs_review before explicit publication approval")
    assembly["status"] = "approved"
    assembly["approved_version"] = assembly.get("version")
    manifest["publish"]["allowed"] = True
    write(path, manifest)


def validate_canonical_request(episode):
    request = read(ROOT / "studio" / "episodes" / episode / "request.json")
    if (request.get("editorial") or {}).get("fallback_policy") != "fail_closed":
        raise RuntimeError("Canonical Satoshi pipeline must fail closed")
    host = request.get("host") or {}
    if host.get("mode") != "scene_image_act_two":
        raise RuntimeError("Canonical Satoshi requires the frozen Tetris image-based Act Two host path")
    if host.get("performance_scope") != "persona_segments":
        raise RuntimeError("Canonical Satoshi requires short persona speaking segments")
    if not request.get("persona_scene"):
        raise RuntimeError("Canonical Satoshi requires a declared episode world")


def run_edit_only_directed(request_path, publish=False):
    """Reassemble a previously generated directed episode with zero new Runway media.

    This path is intentionally narrow: it is for editorial/graphics revisions
    where voice and Satoshi character performance are already persisted.
    """
    args=["python","studio/build_directed_satoshi_episode.py","--request",str(request_path),"--edit-only"]
    if publish:
        args.append("--publish")
    env=dict(os.environ)
    env["PYTHONPATH"]=str(ROOT)
    subprocess.run(args,cwd=ROOT,env=env,check=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--request", required=True, help="Canonical topic/conversation request JSON")
    ap.add_argument("--episode", default="", help="Stable episode ID; defaults from topic")
    ap.add_argument("--publish", action="store_true", help="Explicitly approve and publish after assembly")
    ap.add_argument("--through", default="assembly", choices=MODULES + ["publish"])
    args = ap.parse_args()

    raw = read(args.request)
    if (raw.get("production") or {}).get("mode") == "edit_only":
        run_edit_only_directed(args.request, publish=args.publish)
        return
    episode = args.episode or slug(raw.get("episode_id") or raw.get("title") or raw.get("topic") or "satoshi-episode")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,120}", episode):
        raise ValueError("Invalid episode ID")

    init_episode(args.request, episode)
    validate_canonical_request(episode)

    target = "assembly" if args.through == "publish" else args.through
    for module in MODULES:
        run_module(episode, module)
        if module == "alignment":
            ensure_persona_segments(episode)
        if module == target:
            break

    if args.publish or args.through == "publish":
        approve_for_publish(episode)
        run_module(episode, "publish")

    manifest = read(ROOT / "studio" / "episodes" / episode / "episode_manifest.json")
    print(json.dumps({"episode": episode, "status": manifest["status"], "modules": manifest["modules"]}, indent=2))


if __name__ == "__main__":
    main()
