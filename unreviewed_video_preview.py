"""Build an UNREVIEWED Satoshi video preview from a web-search draft.

This path is for production smoke tests only. It never marks claims reviewed or
content publishable. All inset media are Runway-generated illustrations.
"""
import argparse
import json
import time
from pathlib import Path

import episode
from speech_timing import BEATS
from studio import digest
import visual_director

def build_board(draft):
    if draft.get("status") != "review_required" or draft.get("format") != "short":
        raise ValueError("Expected a review-required web-search short draft")
    script = draft["script"]
    cues = []
    for seg in script["segments"]:
        urls = seg.get("source_urls") or []
        cues.append({
            "cue_id": seg["beat"],
            "spoken_text": seg["text"],
            "claim_ids": ["unreviewed-web:" + digest(url)[:12] for url in urls],
            "source_urls": urls,
            "search_query": seg.get("production_note") or seg["text"],
        })
    return {
        "schema_version": 1,
        "topic": draft["case"]["question"],
        "script_sha256": digest(script),
        "reviewer": "UNREVIEWED_PREVIEW_ONLY",
        "cues": cues,
        "status": "awaiting_footage",
        "publishable": False,
        "review_status": "unreviewed_web_preview",
    }

def visual_prompts(direction):
    visual_director.validate(direction)
    return [(slot["cue_id"], slot["prompt"]) for slot in direction["render_slots"]]

def _records(root, kind):
    ledger = Path(root) / "generated" / "runway"
    rows = []
    if not ledger.exists():
        return rows
    for path in ledger.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("specification", {}).get("kind") == kind:
            rows.append((path, data))
    return rows

def _wait_audio(root, voice_id, timeout_seconds=900, interval=15):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        states = episode.collect_audio(root, voice_id)
        if all(v == "audio_ready" for v in states.values()):
            return states
        terminal = [v for v in states.values() if v in ("failed", "cancelled", "reserved_unknown")]
        if terminal:
            raise RuntimeError("Runway speech task failed or requires reconciliation: " + repr(states))
        time.sleep(interval)
    raise TimeoutError("Timed out waiting for Runway speech tasks")

def _wait_record(root, record, collector, timeout_seconds=900, interval=15):
    deadline = time.time() + timeout_seconds
    relative = str(Path(record).relative_to(Path(root)))
    while time.time() < deadline:
        result = collector(root, relative)
        if result["state"] == "collected":
            return result
        if result["state"] in ("failed", "cancelled", "reserved_unknown"):
            raise RuntimeError("Runway task failed or requires reconciliation: " + repr(result))
        time.sleep(interval)
    raise TimeoutError("Timed out waiting for Runway task")

def build_plan(root, board, visual_results, direction):
    visual_director.validate(direction)
    if len(visual_results) != 6:
        raise ValueError("Exactly six generated visual previews required")
    shots = []
    for index, item in enumerate(visual_results):
        candidate = item["candidate"]
        slot = direction["render_slots"][index]
        cue_id = candidate["cue_id"]
        if cue_id != slot["cue_id"]:
            raise ValueError("Generated visual order does not match visual direction")
        cue = next(c for c in board["cues"] if c["cue_id"] == cue_id)
        shots.append({
            "candidate_id": candidate["id"],
            "cue_id": cue_id,
            "claim_ids": cue["claim_ids"],
            "media_source": candidate["media_source"],
            "rights_status": "preview_generated",
            "license_basis": "Runway-generated illustration for private preview",
            "credit": "AI-GENERATED ILLUSTRATION",
            "visual_type": "illustration",
            "start_seconds": 0,
            "destination_seconds": index * 5,
            "duration_seconds": 5,
            "selection_basis": "deterministic_visual_director",
            "visual_function": slot["visual_function"],
            "monologue_move": slot["move"],
            "overlay_text": slot["overlay_text"],
        })
    return {
        "schema_version": 1,
        "topic": board["topic"],
        "script_sha256": board["script_sha256"],
        "reviewer": "UNREVIEWED_PREVIEW_ONLY",
        "target_seconds": 30,
        "shots": shots,
        "status": "renderable_not_publish_approved",
        "publishable": False,
        "headline": "UNREVIEWED SATOSHI PREVIEW",
    }

def run(draft_path, root, voice_id, avatar_id, live=False, render=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    board = build_board(draft)
    direction = visual_director.plan(draft["script"])
    visual_director.validate(direction)
    (root / "storyboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    (root / "visual-direction.json").write_text(
        json.dumps(direction, indent=2) + "\n", encoding="utf-8")
    (root / "graphics.json").write_text(
        json.dumps({"headline": "UNREVIEWED SATOSHI PREVIEW"}, indent=2) + "\n", encoding="utf-8")
    if not live:
        audio = episode.submit_audio(root, voice_id, live=False)
        visuals = [episode.submit_visual(root, cue, prompt, live=False)
                   for cue, prompt in visual_prompts(direction)]
        return {"status": "dry_run", "audio": audio, "visuals": visuals,
                "publishable": False, "episode_dir": str(root)}

    episode.submit_audio(root, voice_id, live=True)
    _wait_audio(root, voice_id)
    visual_records = []
    for cue, prompt in visual_prompts(direction):
        result = episode.submit_visual(root, cue, prompt, live=True)
        if not result.get("record"):
            raise RuntimeError("Visual submission did not return a durable record")
        visual_records.append(result["record"])
    visual_results = [_wait_record(root, rec, episode.collect_visual) for rec in visual_records]

    # Narration is assembled only after all five speech beats are collected.
    episode.narration(root)
    host = episode.submit_host(root, "avatar", live=True, avatar_id=avatar_id)
    if not host.get("record"):
        raise RuntimeError("Avatar submission did not return a durable record")
    _wait_record(root, host["record"], episode.collect_host)

    plan = build_plan(root, board, visual_results, direction)
    (root / "footage-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    result = episode.render(root, "remotion", video=render)
    return {"status": "rendered" if render else "ready_to_render",
            "render": result, "publishable": False, "episode_dir": str(root)}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft", required=True)
    p.add_argument("--input-dir", default="outputs/unreviewed-video-preview")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--avatar-id", required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(args.draft, args.input_dir, args.voice_id, args.avatar_id,
                             live=args.live, render=args.render), indent=2))
    except (ValueError, OSError, RuntimeError, TimeoutError, KeyError, TypeError) as exc:
        p.exit(1, "Unreviewed video preview blocked: %s\n" % exc)

if __name__ == "__main__":
    main()
