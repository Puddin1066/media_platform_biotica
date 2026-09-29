"""Build an UNREVIEWED Satoshi video preview from a web-search draft.

This path is for production smoke tests only. It never marks claims reviewed or
content publishable.

Visual modes (SATOSHI_VISUAL_MODE / --visual-mode):
  lean — Wikimedia Commons stills → ffmpeg loops for insets; Runway for host only
         (an explicit no-candidates result falls back to local neutral cards)
  ai   — six Gen-4.5 illustrative insets (legacy high-spend path)
"""
import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

import episode
import lean_visuals
from speech_timing import BEATS
from studio import digest
import visual_director

GEN45_CREDITS_PER_SECOND = 12
VISUAL_SECONDS = 5
VISUAL_CREDITS = GEN45_CREDITS_PER_SECOND * VISUAL_SECONDS
DEFAULT_RUNWAY_MAX_CREDITS = 420
RUNWAY_VISUAL_PROMPT_MAX_CHARS = 1000
RUNWAY_PROMPT_COMPACTION_MARKER = " ... "
RUNWAY_PROMPT_SUFFIX_CHARS = 320
DEFAULT_RUNWAY_TASK_TIMEOUT_SECONDS = 1800
MAX_RUNWAY_TASK_TIMEOUT_SECONDS = 7200
DEFAULT_RUNWAY_POLL_INTERVAL_SECONDS = 15
MAX_RUNWAY_POLL_INTERVAL_SECONDS = 300
VISUAL_MODES = ("lean", "ai")
DEFAULT_VISUAL_MODE = "lean"
LOCAL_PLACEHOLDER_COLORS = (
    "0x243447",
    "0x34495e",
    "0x3d405b",
    "0x264653",
    "0x4a4e69",
    "0x2f3e46",
)


def resolve_visual_mode(supplied=None):
    raw = (supplied if supplied is not None
           else os.environ.get("SATOSHI_VISUAL_MODE", DEFAULT_VISUAL_MODE))
    mode = str(raw or DEFAULT_VISUAL_MODE).strip().casefold()
    if mode not in VISUAL_MODES:
        raise ValueError("SATOSHI_VISUAL_MODE must be lean or ai")
    return mode


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


def _provider_visual_prompt(prompt):
    """Fit an enriched direction into Runway's prompt contract deterministically.

    Prompts already accepted by the provider are returned unchanged, preserving
    ledger identities and cached media. For an over-limit prompt, whitespace is
    compacted first. If it is still too long, retain both the opening direction
    and the trailing constraints. The complete unabridged prompt remains in
    visual-direction.json for review and provenance.
    """
    if not isinstance(prompt, str) or not prompt.strip():
        raise ValueError("Visual prompt must be substantive text")
    prompt = prompt.strip()
    if len(prompt) <= RUNWAY_VISUAL_PROMPT_MAX_CHARS:
        return prompt

    compacted = " ".join(prompt.split())
    if len(compacted) <= RUNWAY_VISUAL_PROMPT_MAX_CHARS:
        return compacted

    suffix_budget = RUNWAY_PROMPT_SUFFIX_CHARS
    head_budget = (
        RUNWAY_VISUAL_PROMPT_MAX_CHARS
        - len(RUNWAY_PROMPT_COMPACTION_MARKER)
        - suffix_budget
    )
    head = compacted[:head_budget]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    tail = compacted[-suffix_budget:]
    if " " in tail:
        tail = tail.split(" ", 1)[1]
    bounded = head.rstrip() + RUNWAY_PROMPT_COMPACTION_MARKER + tail.lstrip()
    if not 1 <= len(bounded) <= RUNWAY_VISUAL_PROMPT_MAX_CHARS:
        raise ValueError("Could not compile visual prompt within provider limit")
    return bounded


def visual_prompts(direction):
    visual_director.validate(direction)
    return [
        (slot["cue_id"], _provider_visual_prompt(slot["prompt"]))
        for slot in direction["render_slots"]
    ]


def estimated_runway_credits(board, visual_count=6, visual_mode=DEFAULT_VISUAL_MODE):
    """Conservative predictable spend bound for this preview.

    Gen-4.5 is 12 credits/s; each AI visual is 5s. Lean mode spends zero Gen-4.5
    credits on insets. Multilingual-v2 speech is 1 credit/50 characters. Avatar
    pricing is bounded here at 12 credits for a <=30s preview (2 upfront + 2 per
    6s). This intentionally rounds upward.
    """
    speech_chars = sum(len(c.get("spoken_text", "")) for c in board.get("cues", []))
    tts = sum(math.ceil(len(c.get("spoken_text", "")) / 50)
              for c in board.get("cues", []) if c.get("spoken_text"))
    visuals = visual_count * VISUAL_CREDITS
    avatar_max = 12
    return {"visuals": visuals, "tts": tts, "avatar_max": avatar_max,
            "total_max": visuals + tts + avatar_max, "speech_chars": speech_chars,
            "visual_mode": visual_mode, "visual_count": visual_count}


def enforce_runway_budget(board, visual_count=6, visual_mode=DEFAULT_VISUAL_MODE):
    estimate = estimated_runway_credits(board, visual_count, visual_mode=visual_mode)
    raw = os.environ.get("RUNWAY_MAX_CREDITS", str(DEFAULT_RUNWAY_MAX_CREDITS))
    try:
        cap = int(raw)
    except ValueError as exc:
        raise ValueError("RUNWAY_MAX_CREDITS must be an integer") from exc
    if cap <= 0:
        raise ValueError("RUNWAY_MAX_CREDITS must be positive")
    if estimate["total_max"] > cap:
        raise RuntimeError(
            "Runway spend governor blocked preview before provider calls: "
            f"estimated maximum {estimate['total_max']} credits exceeds cap {cap}")
    canary = 0 if visual_count == 0 else VISUAL_CREDITS
    return {**estimate, "cap": cap, "canary_credits": canary}


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


def _bounded_wait_setting(name, supplied, default, maximum):
    raw = supplied if supplied is not None else os.environ.get(name, str(default))
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not 0 < value <= maximum:
        raise ValueError(f"{name} must be greater than zero and at most {maximum}")
    return value


def _wait_audio(root, voice_id, timeout_seconds=None, interval=None):
    timeout_seconds = _bounded_wait_setting(
        "RUNWAY_TASK_TIMEOUT_SECONDS", timeout_seconds,
        DEFAULT_RUNWAY_TASK_TIMEOUT_SECONDS, MAX_RUNWAY_TASK_TIMEOUT_SECONDS)
    interval = _bounded_wait_setting(
        "RUNWAY_POLL_INTERVAL_SECONDS", interval,
        DEFAULT_RUNWAY_POLL_INTERVAL_SECONDS, MAX_RUNWAY_POLL_INTERVAL_SECONDS)
    deadline = time.monotonic() + timeout_seconds
    while True:
        states = episode.collect_audio(root, voice_id)
        if all(v == "audio_ready" for v in states.values()):
            return states
        terminal = [v for v in states.values()
                    if v in ("failed", "cancelled", "reserved_unknown", "rejected_no_task")]
        if terminal:
            raise RuntimeError("Runway speech task failed or requires reconciliation: " + repr(states))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    raise TimeoutError(
        f"Timed out after {timeout_seconds:g}s waiting for existing Runway speech tasks: "
        + repr(states))


def _wait_record(root, record, collector, timeout_seconds=None, interval=None):
    timeout_seconds = _bounded_wait_setting(
        "RUNWAY_TASK_TIMEOUT_SECONDS", timeout_seconds,
        DEFAULT_RUNWAY_TASK_TIMEOUT_SECONDS, MAX_RUNWAY_TASK_TIMEOUT_SECONDS)
    interval = _bounded_wait_setting(
        "RUNWAY_POLL_INTERVAL_SECONDS", interval,
        DEFAULT_RUNWAY_POLL_INTERVAL_SECONDS, MAX_RUNWAY_POLL_INTERVAL_SECONDS)
    deadline = time.monotonic() + timeout_seconds
    resolved_root = Path(root).resolve()
    resolved_record = Path(record).resolve()
    relative = str(resolved_record.relative_to(resolved_root))
    while True:
        result = collector(resolved_root, relative)
        if result["state"] == "collected":
            return result
        if result["state"] in ("failed", "cancelled", "reserved_unknown", "rejected_no_task"):
            raise RuntimeError("Runway task failed or requires reconciliation: " + repr(result))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    raise TimeoutError(
        f"Timed out after {timeout_seconds:g}s waiting for existing Runway task "
        f"{result.get('task_id') or relative}; state={result.get('state')}")


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
        provider = candidate.get("provider") or "runway"
        visual_type = (item.get("visual_type")
                       or candidate.get("visual_type")
                       or ("source" if provider == "commons" else "illustration"))
        if provider == "commons":
            license_basis = (item.get("license_basis")
                             or "Wikimedia Commons still for private preview")
            credit = item.get("credit") or "Wikimedia Commons"
            selection_basis = "commons_still_lean_visuals"
        elif provider == "local_placeholder":
            license_basis = (item.get("license_basis")
                             or "Locally generated neutral card for unreviewed preview")
            credit = (item.get("credit")
                      or "LOCAL PREVIEW PLACEHOLDER — NO EVIDENCE")
            selection_basis = "local_placeholder_after_empty_commons_result"
        else:
            license_basis = (item.get("license_basis")
                             or "Runway-generated illustration for private preview")
            credit = item.get("credit") or "AI-GENERATED ILLUSTRATION"
            selection_basis = "deterministic_visual_director"
        shots.append({
            "candidate_id": candidate["id"],
            "cue_id": cue_id,
            "claim_ids": cue["claim_ids"],
            "media_source": candidate["media_source"],
            "rights_status": item.get("rights_status") or "preview_generated",
            "license_basis": license_basis,
            "credit": credit,
            "visual_type": visual_type,
            "start_seconds": 0,
            "destination_seconds": index * 5,
            "duration_seconds": 5,
            "selection_basis": selection_basis,
            "visual_function": slot["visual_function"],
            "monologue_move": slot["move"],
            "overlay_text": slot["overlay_text"],
            "provider": provider,
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


def _is_empty_commons_result(exc):
    """Recognize only the explicit zero-candidate condition safe to replace."""
    return "no commons image candidates for cue " in str(exc or "").casefold()


def _local_preview_placeholders(root, direction, draft_topic, commons_error):
    """Create free, evidence-neutral cards after an explicit empty Commons result.

    These cards are not presented as source footage or factual receipts. The
    original Commons failure is retained in a sidecar, and deterministic local
    files are reused on resume instead of making a paid visual-provider call.
    """
    visual_director.validate(direction)
    root = Path(root)
    output_dir = root / "generated" / "lean-fallback"
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    for index, slot in enumerate(direction["render_slots"]):
        cue_id = slot["cue_id"]
        target = output_dir / f"{index:02d}-{cue_id}.mp4"
        if not target.is_file() or target.stat().st_size == 0:
            part = target.with_suffix(".part.mp4")
            part.unlink(missing_ok=True)
            proc = subprocess.run([
                "ffmpeg", "-nostdin", "-loglevel", "error", "-y",
                "-f", "lavfi",
                "-i", (
                    f"color=c={LOCAL_PLACEHOLDER_COLORS[index % len(LOCAL_PLACEHOLDER_COLORS)]}"
                    ":s=1280x720:r=30"
                ),
                "-frames:v", str(VISUAL_SECONDS * 30),
                "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(part),
            ], text=True, capture_output=True)
            if proc.returncode != 0:
                part.unlink(missing_ok=True)
                raise RuntimeError(
                    "Could not generate local unreviewed-preview placeholder: "
                    + (proc.stderr or f"ffmpeg exit {proc.returncode}").strip())
            part.replace(target)

        relative = str(target.relative_to(root))
        candidate = {
            "id": "local-preview:" + digest({
                "topic": draft_topic,
                "cue_id": cue_id,
                "prompt": slot["prompt"],
                "purpose": "UNREVIEWED_PREVIEW_ONLY",
            }),
            "provider": "local_placeholder",
            "cue_id": cue_id,
            "media_source": relative,
            "rights_status": "preview_generated",
            "visual_type": "illustration",
            "note": (
                "Neutral local placeholder generated after Commons returned no "
                "candidates; it is not evidence or source footage."
            ),
        }
        results.append({
            "state": "collected",
            "candidate": candidate,
            "visual_type": "illustration",
            "rights_status": "preview_generated",
            "license_basis": "Locally generated neutral card for unreviewed preview",
            "credit": "LOCAL PREVIEW PLACEHOLDER — NO EVIDENCE",
        })

    evidence = {
        "schema_version": 1,
        "purpose": "UNREVIEWED_PREVIEW_ONLY",
        "trigger": "explicit_empty_commons_candidate_result",
        "commons_error": str(commons_error),
        "topic": draft_topic,
        "fallback": "local_neutral_cards",
        "provider_calls_added": 0,
        "files": [item["candidate"]["media_source"] for item in results],
        "rights_status": "preview_generated",
        "publishable": False,
    }
    (output_dir / "fallback-evidence.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return results


def _collect_lean_visuals(root, direction, draft_topic, live):
    try:
        return lean_visuals.collect_commons_insets(
            root, direction, draft_topic=draft_topic, live=live)
    except (RuntimeError, ValueError) as exc:
        if not _is_empty_commons_result(exc):
            raise
        return _local_preview_placeholders(root, direction, draft_topic, exc)


def _submit_and_collect_visual(root, cue, prompt):
    result = episode.submit_visual(root, cue, prompt, live=True)
    if not result.get("record"):
        raise RuntimeError("Visual submission did not return a durable record")
    return _wait_record(root, result["record"], episode.collect_visual)


def run(draft_path, root, voice_id, avatar_id, live=False, render=False, visual_mode=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    board = build_board(draft)
    direction = visual_director.plan(draft["script"])
    visual_director.validate(direction)
    mode = resolve_visual_mode(visual_mode)
    prompts = visual_prompts(direction)
    visual_count = 0 if mode == "lean" else len(prompts)
    budget = enforce_runway_budget(board, visual_count, visual_mode=mode)
    (root / "storyboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    (root / "visual-direction.json").write_text(
        json.dumps(direction, indent=2) + "\n", encoding="utf-8")
    (root / "runway-budget.json").write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
    (root / "graphics.json").write_text(
        json.dumps({"headline": "UNREVIEWED SATOSHI PREVIEW"}, indent=2) + "\n", encoding="utf-8")
    if not live:
        audio = episode.submit_audio(root, voice_id, live=False)
        if mode == "lean":
            visuals = _collect_lean_visuals(root, direction, board["topic"], live=False)
        else:
            visuals = [episode.submit_visual(root, cue, prompt, live=False)
                       for cue, prompt in prompts]
        return {"status": "dry_run", "audio": audio, "visuals": visuals,
                "visual_mode": mode, "runway_budget": budget,
                "publishable": False, "episode_dir": str(root)}

    if mode == "lean":
        # Commons/web stills first — no Gen-4.5 canary. An explicit empty result
        # uses evidence-neutral local cards and does not add provider spend.
        visual_results = _collect_lean_visuals(root, direction, board["topic"], live=True)
        episode.submit_audio(root, voice_id, live=True)
        _wait_audio(root, voice_id)
    else:
        # Canary-first Gen-4.5: prove one task before narration / remaining insets.
        visual_results = [_submit_and_collect_visual(root, *prompts[0])]
        episode.submit_audio(root, voice_id, live=True)
        _wait_audio(root, voice_id)
        for cue, prompt in prompts[1:]:
            visual_results.append(_submit_and_collect_visual(root, cue, prompt))

    # A previously collected host plate is a reusable visual asset. Do not spend
    # again merely because the final edit now follows a longer narration timeline.
    existing_host = root / "generated" / "host.mp4"
    if not existing_host.is_file():
        # Host generation may still use the bounded provider narration path; the
        # final Remotion narration is rebuilt from the original speech beats.
        episode.narration(root)
        host = episode.submit_host(root, "avatar", live=True, avatar_id=avatar_id)
        if not host.get("record"):
            raise RuntimeError("Avatar submission did not return a durable record")
        _wait_record(root, host["record"], episode.collect_host)

    plan = build_plan(root, board, visual_results, direction)
    (root / "footage-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    result = episode.render(root, "remotion", video=render)
    return {"status": "rendered" if render else "ready_to_render",
            "render": result, "runway_budget": budget, "visual_mode": mode,
            "publishable": False, "episode_dir": str(root)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft", required=True)
    p.add_argument("--input-dir", default="outputs/unreviewed-video-preview")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--avatar-id", required=True)
    p.add_argument("--visual-mode", choices=VISUAL_MODES,
                   default=None, help="lean (Commons insets) or ai (Gen-4.5)")
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(args.draft, args.input_dir, args.voice_id, args.avatar_id,
                             live=args.live, render=args.render,
                             visual_mode=args.visual_mode), indent=2))
    except (ValueError, OSError, RuntimeError, TimeoutError, KeyError, TypeError) as exc:
        p.exit(1, "Unreviewed video preview blocked: %s\n" % exc)


if __name__ == "__main__":
    main()
