"""Pipeline B: immutable production renderer for approved Satoshi editorial packages.

Consumes Pipeline A's approved artifact plus the original canonical request. It
verifies request/script/prosody/audio hashes, converts the locked script into the
existing production timing contract without changing any words, generates visual
stills, reuses an available host plate, renders in Remotion, persists media, and
may publish. No text-generation model is called here, and no new host video is
generated when a plate is already stored.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path

import canonical_satoshi_lipsync_runtime as lipsync
import canonical_satoshi_runtime as production
import satoshi_editorial_pipeline as editorial

ROLES = production.STORY_ROLES
CUES = production.PRODUCTION_BEATS


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_package(package, request_path):
    package = Path(package)
    manifest = read_json(package / "manifest.json")
    status = str(manifest.get("status") or "")
    if status != "editorially_approved_with_audio_model_judge":
        raise ValueError(f"Pipeline B requires audio-model-approved Pipeline A package, got {status!r}")
    if manifest.get("audio_judge_requests_regeneration"):
        raise ValueError("Pipeline A audio judge requested regeneration; production is blocked")

    request = read_json(request_path)
    if editorial.sha(request) != manifest.get("request_sha256"):
        raise ValueError("Pipeline A request hash does not match production request")

    script_path = package / manifest["canonical_script"]
    prosody_path = package / manifest["performance_score"]
    audio_path = package / manifest["selected_audio"]
    for path in (script_path, prosody_path, audio_path):
        if not path.is_file() or path.stat().st_size <= 0:
            raise ValueError(f"Pipeline A artifact missing: {path}")

    script = read_json(script_path)
    prosody = read_json(prosody_path)
    if editorial.sha(script) != manifest.get("script_sha256"):
        raise ValueError("Locked script hash mismatch")
    if editorial.sha(prosody) != manifest.get("performance_sha256"):
        raise ValueError("Performance-score hash mismatch")
    if file_sha(audio_path) != manifest.get("audio_sha256"):
        raise ValueError("Selected narration hash mismatch")
    return manifest, request, script, prosody, audio_path


def _partition(items, groups):
    if len(items) < groups:
        raise ValueError(f"Locked script needs at least {groups} sentences for current production grammar")
    out, cursor = [], 0
    for i in range(groups):
        remaining = len(items) - cursor
        remaining_groups = groups - i
        size = math.ceil(remaining / remaining_groups)
        out.append(items[cursor:cursor + size])
        cursor += size
    return out


def locked_story(script, visual_intents):
    sentences = script.get("script") or []
    chunks = _partition(sentences, len(ROLES))
    visual_by_id = {}
    if isinstance(visual_intents, list):
        for item in visual_intents:
            if isinstance(item, dict) and item.get("sentence_id"):
                visual_by_id[item["sentence_id"]] = item

    beats = []
    for index, (role, chunk) in enumerate(zip(ROLES, chunks), 1):
        text = " ".join(str(s.get("text") or "").strip() for s in chunk).strip()
        if not text:
            raise ValueError("Locked script partition produced empty beat")
        citations = sorted({url for s in chunk for url in (s.get("citations") or []) if isinstance(url, str)})
        intents = [visual_by_id.get(s.get("sentence_id"), {}) for s in chunk]
        description = "; ".join(str(v.get("intent") or v.get("visual") or "").strip() for v in intents if v)
        if not description:
            description = f"Editorial illustration supporting this exact {role.replace('_', ' ')} narration without fabricated data."
        beats.append({
            "beat_id": f"b{index:02d}",
            "role": role,
            "spoken_text": text,
            "source_message_ids": [],
            "claim_status": "verified" if citations else "rhetorical",
            "citations": citations,
            "humor_score": 0.7 if role in {"weird_part", "button"} else 0.2,
            "insight_score": 0.9 if role in {"synthesis", "button"} else 0.5,
            "visual_intent": description,
            "image_prompt": "Documentary editorial illustration, vertical-video evidence insert. " + description + " No text, no logos, no fabricated chart values, no identifiable real person.",
            "overlay_motion": "slow_zoom" if role in {"hook", "synthesis"} else "hold" if role in {"receipt", "objection"} else "crossfade",
        })
    joined_source = " ".join(str(s.get("text") or "").strip() for s in sentences).strip()
    joined_story = " ".join(beat["spoken_text"] for beat in beats).strip()
    if joined_source != joined_story:
        raise RuntimeError("Production adaptation changed locked narration words or order")
    return {
        "schema_version": 1,
        "title": str(script.get("title") or "Satoshi").strip(),
        "thesis": str(script.get("thesis") or "").strip(),
        "mens_health_bridge": "",
        "beats": beats,
        "sources": [],
        "provider_mode": "pipeline_a_locked",
    }


def _audio_duration(path):
    result = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)
    ], check=True, capture_output=True, text=True, timeout=60)
    return float(result.stdout.strip())


def split_audio_for_host(root, voice, production_blocks):
    """Create five driver/timing segments from the immutable master narration.

    The final Reel always uses the untouched selected WAV. These segments exist only
    for host-driving and timing compatibility with the existing production stack.
    """
    root = Path(root)
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    seconds = _audio_duration(voice)
    weights = [max(1, len(block["spoken_text"].split())) for block in production_blocks]
    total = sum(weights)
    cursor = 0.0
    outputs = {}
    for i, (block, weight) in enumerate(zip(production_blocks, weights)):
        duration = seconds - cursor if i == len(production_blocks) - 1 else seconds * weight / total
        target = audio_dir / f"{block['cue_id']}.mp3"
        subprocess.run([
            "ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-ss", f"{cursor:.6f}",
            "-t", f"{max(0.1, duration):.6f}", "-i", str(voice), "-vn", "-c:a", "libmp3lame", "-q:a", "2", str(target)
        ], check=True, timeout=180)
        outputs[block["cue_id"]] = str(target)
        cursor += duration
    return outputs


def production_host_request(request):
    """Pipeline B always reuses a stored plate instead of generating a host video."""
    host = dict(request.get("host") or {})
    host["mode"] = "master_asset"
    resolved = dict(request)
    resolved["host"] = host
    return resolved


def run(package, request_path, output="outputs/satoshi-production", live=False, publish=False):
    manifest_a, request, locked, prosody, selected_audio = verify_package(package, request_path)
    visual_intents_path = Path(package) / manifest_a.get("visual_intents", "visual_intents.json")
    visual_intents = read_json(visual_intents_path) if visual_intents_path.is_file() else []

    episode_id = production.episode_id(request)
    root = Path(output) / episode_id
    root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(request_path, root / "request.json")
    shutil.copyfile(Path(package) / "manifest.json", root / "pipeline-a-manifest.json")
    shutil.copyfile(Path(package) / manifest_a["canonical_script"], root / "canonical-script.json")
    shutil.copyfile(Path(package) / manifest_a["performance_score"], root / "performance-score.json")

    story = locked_story(locked, visual_intents)
    production._write_json(root / "story.json", story)
    blocks = production.compile_production(story)
    production._write_json(root / "production-beats.json", blocks)
    board = production.storyboard(blocks, story)
    production._write_json(root / "storyboard.json", board)

    plan = {
        "schema_version": 1,
        "episode_id": episode_id,
        "pipeline_a_audio_sha256": manifest_a["audio_sha256"],
        "pipeline_a_script_sha256": manifest_a["script_sha256"],
        "immutable_narration": True,
        "status": "planned",
    }
    if not live:
        production._write_json(root / "manifest.json", plan)
        return plan

    voice = root / "generated" / "voice.wav"
    voice.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(selected_audio, voice)
    if file_sha(voice) != manifest_a["audio_sha256"]:
        raise RuntimeError("Narration changed while entering Pipeline B")

    split_audio_for_host(root, voice, blocks)
    stills = production.ensure_stills(root, story, live=True)
    host = lipsync.ensure_continuous_host(root, board, production_host_request(request), live=True)
    if not host.get("file"):
        raise RuntimeError("Host generation produced no file")

    timing = production._timing(root, blocks, story)
    production._write_json(root / "timing.json", timing)
    production.prepare_remotion(root, story, blocks, timing, stills, host["file"], voice)
    video = production.render_reel()

    lipsync._LAST_STORY = story
    media = lipsync.persist_final_with_distribution(root, video, episode_id)
    plan.update({"status": "rendered", "host": host, "final_media": media})

    should_publish = bool(publish or (request.get("production") or {}).get("publish_instagram"))
    if should_publish:
        plan["instagram"] = lipsync.publish_final_with_distribution(root, story, video, media)
        plan["status"] = "published"
    production._write_json(root / "manifest.json", plan)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True, help="Downloaded Pipeline A artifact directory")
    parser.add_argument("--request", required=True, help="Original canonical request used by Pipeline A")
    parser.add_argument("--output", default="outputs/satoshi-production")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = run(args.package, args.request, args.output, args.live, args.publish)
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Satoshi Production Pipeline B blocked: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
