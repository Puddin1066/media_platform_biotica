"""Build an UNREVIEWED Satoshi video preview from a web-search draft.

This path is for production smoke tests only. It never marks claims reviewed or
content publishable. Runway-generated illustrations are preferred. If Runway
returns a definitive credit-exhaustion rejection, already collected media are
reused and missing preview-only assets are filled with explicit local
placeholders so the private render can still be inspected without another
provider call.
"""
import argparse
import json
import math
import os
import subprocess
import time
from pathlib import Path

import episode
import runway_media
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
LOCAL_FALLBACK_AUDIO_SECONDS = 5
LOCAL_FALLBACK_HOST_SECONDS = 30
LOCAL_FALLBACK_COLORS = (
    "25344f", "4b304d", "23463f", "58422c", "3e3f63", "56363a",
)


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


def estimated_runway_credits(board, visual_count=6):
    """Conservative predictable spend bound for this preview.

    Gen-4.5 is 12 credits/s; each visual is 5s. Multilingual-v2 speech is
    1 credit/50 characters. Avatar pricing is bounded here at 12 credits for a
    <=30s preview (2 upfront + 2 per 6s). This intentionally rounds upward.
    """
    speech_chars = sum(len(c.get("spoken_text", "")) for c in board.get("cues", []))
    tts = sum(math.ceil(len(c.get("spoken_text", "")) / 50)
              for c in board.get("cues", []) if c.get("spoken_text"))
    visuals = visual_count * VISUAL_CREDITS
    avatar_max = 12
    return {"visuals": visuals, "tts": tts, "avatar_max": avatar_max,
            "total_max": visuals + tts + avatar_max, "speech_chars": speech_chars}


def enforce_runway_budget(board, visual_count=6):
    estimate = estimated_runway_credits(board, visual_count)
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
    return {**estimate, "cap": cap, "canary_credits": VISUAL_CREDITS}


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
        local_placeholder = candidate.get("provider") == "local_placeholder"
        shots.append({
            "candidate_id": candidate["id"],
            "cue_id": cue_id,
            "claim_ids": cue["claim_ids"],
            "media_source": candidate["media_source"],
            "rights_status": "preview_placeholder" if local_placeholder else "preview_generated",
            "license_basis": (
                "Locally generated synthetic placeholder for private unreviewed preview"
                if local_placeholder else
                "Runway-generated illustration for private preview"
            ),
            "credit": (
                "LOCAL PLACEHOLDER — NOT EVIDENCE"
                if local_placeholder else
                "AI-GENERATED ILLUSTRATION"
            ),
            "visual_type": "illustration",
            "start_seconds": 0,
            "destination_seconds": index * 5,
            "duration_seconds": 5,
            "selection_basis": (
                "deterministic_credit_exhaustion_placeholder"
                if local_placeholder else
                "deterministic_visual_director"
            ),
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


def _provider_credit_exhausted(value, status=None):
    """Recognize only Runway's definitive no-credit pre-task rejection."""
    if status is None:
        status = getattr(value, "status_code", None)
    text = str(value or "").casefold()
    phrase = (
        "do not have enough credits to run this task" in text or
        "not enough credits to run this task" in text
    )
    explicit_400 = status == 400 or "error code: 400" in text
    return phrase and explicit_400


def _existing_credit_exhaustion(root):
    """Return preserved credit-exhaustion evidence without retrying Runway."""
    ledger = Path(root) / "generated" / "runway"
    if not ledger.exists():
        return None
    for path in sorted(ledger.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("state") != "rejected_no_task":
            continue
        error = data.get("error", "")
        if _provider_credit_exhausted(error, data.get("provider_http_status")):
            return {"record": str(path), "error": error,
                    "provider_http_status": data.get("provider_http_status")}
    return None


def _run_ffmpeg_output(path, arguments):
    """Create one local preview asset atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.stem + ".part" + path.suffix)
    part.unlink(missing_ok=True)
    proc = subprocess.run(
        ["ffmpeg", "-nostdin", "-loglevel", "error", "-y", *arguments, str(part)],
        text=True, capture_output=True)
    if proc.returncode != 0:
        part.unlink(missing_ok=True)
        raise RuntimeError(
            "Could not create deterministic local preview placeholder: " +
            (proc.stderr or f"ffmpeg exit {proc.returncode}").strip())
    if not part.is_file() or part.stat().st_size == 0:
        part.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg produced an empty local preview placeholder")
    part.replace(path)
    return path


def _ensure_placeholder_video(path, color, width, height, seconds):
    path = Path(path)
    if path.is_file() and path.stat().st_size > 0:
        return path
    return _run_ffmpeg_output(path, [
        "-f", "lavfi", "-i",
        f"color=c=0x{color}:s={width}x{height}:r=30:d={seconds}",
        "-t", str(seconds), "-an", "-c:v", "libx264",
        "-preset", "veryfast", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    ])


def _ensure_placeholder_audio(root):
    """Fill only missing beats; collected provider speech remains untouched."""
    root = Path(root)
    result = {}
    for index, beat in enumerate(BEATS):
        existing = episode.beat_file(root, beat)
        if existing is not None:
            result[beat] = {"source": str(existing.relative_to(root)),
                            "provider_media_reused": True}
            continue
        target = root / "audio" / (beat + ".wav")
        frequency = 220 + index * 35
        _run_ffmpeg_output(target, [
            "-f", "lavfi", "-i",
            f"sine=frequency={frequency}:sample_rate=48000:duration={LOCAL_FALLBACK_AUDIO_SECONDS}",
            "-filter:a", "volume=0.08", "-ac", "1", "-c:a", "pcm_s16le",
        ])
        result[beat] = {"source": str(target.relative_to(root)),
                        "provider_media_reused": False,
                        "kind": "audible_placeholder_tone_not_speech"}
    return result


def _reuse_collected_visual(root, board, cue, prompt):
    """Recover a completed local visual without retrieving anything from Runway."""
    ledger = Path(root) / "generated" / "runway"
    preview = runway_media.submit_visual(board, cue, prompt, ledger, live=False)
    record = episode.record_for(Path(root), preview["specification"])
    if not record.is_file():
        return None
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if data.get("state") != "collected":
        return None
    try:
        result = episode.collect_visual(root, str(record.relative_to(Path(root))))
    except (OSError, RuntimeError, ValueError, KeyError):
        return None
    return result if result.get("state") == "collected" and result.get("candidate") else None


def _placeholder_visual(root, board, index, cue, prompt):
    token = board["script_sha256"][:12]
    target = Path(root) / "generated" / f"fallback-visual-{index + 1}-{token}.mp4"
    _ensure_placeholder_video(
        target, LOCAL_FALLBACK_COLORS[index % len(LOCAL_FALLBACK_COLORS)],
        1280, 720, VISUAL_SECONDS)
    candidate = {
        "id": "local-placeholder:" + runway_media.digest_file(target),
        "provider": "local_placeholder",
        "cue_id": cue,
        "media_source": str(target.relative_to(Path(root))),
        "rights_status": "preview_placeholder",
        "visual_type": "illustration",
        "prompt": prompt,
        "note": (
            "Synthetic local color placeholder created after a definitive Runway "
            "credit-exhaustion rejection; not evidence and not publishable."
        ),
    }
    return {"state": "collected", "task_id": None,
            "file": str(target), "candidate": candidate}


def _render_credit_fallback(root, board, prompts, direction, budget, render,
                            trigger, completed_visuals=None):
    """Resume as a conspicuously local, nonpublishable preview without providers."""
    root = Path(root)
    completed_visuals = list(completed_visuals or [])
    visual_results = []
    visual_evidence = []

    for index, (cue, prompt) in enumerate(prompts):
        result = None
        if index < len(completed_visuals):
            supplied = completed_visuals[index]
            candidate = supplied.get("candidate", {})
            if supplied.get("state") == "collected" and candidate.get("cue_id") == cue:
                result = supplied
        if result is None:
            result = _reuse_collected_visual(root, board, cue, prompt)
        if result is None:
            result = _placeholder_visual(root, board, index, cue, prompt)
        visual_results.append(result)
        visual_evidence.append({
            "cue_id": cue,
            "provider": result["candidate"].get("provider"),
            "media_source": result["candidate"]["media_source"],
        })

    audio_evidence = _ensure_placeholder_audio(root)
    narration = episode.narration(root)

    plate = root / "plate.mp4"
    generated_host = root / "generated" / "host.mp4"
    host_reused = plate.is_file() or generated_host.is_file()
    if not host_reused:
        _ensure_placeholder_video(
            generated_host, "111622", 1080, 1920, LOCAL_FALLBACK_HOST_SECONDS)

    plan = build_plan(root, board, visual_results, direction)
    plan["headline"] = "UNREVIEWED PREVIEW — LOCAL PLACEHOLDER MEDIA"
    (root / "footage-plan.json").write_text(
        json.dumps(plan, indent=2) + "\n", encoding="utf-8")

    ledger = root / "generated" / "runway"
    preserved_records = ([str(path.relative_to(root)) for path in sorted(ledger.glob("*.json"))]
                         if ledger.exists() else [])
    evidence = {
        "schema_version": 1,
        "status": "local_placeholder_fallback_ready",
        "reason": "definitive_runway_credit_exhaustion",
        "trigger": trigger,
        "script_sha256": board["script_sha256"],
        "provider_calls_after_fallback": 0,
        "preserved_runway_records": preserved_records,
        "visuals": visual_evidence,
        "audio": audio_evidence,
        "narration": str(narration.relative_to(root)),
        "host_provider_media_reused": host_reused,
        "scope": "UNREVIEWED_PREVIEW_ONLY",
        "review_status": "unreviewed_web_preview",
        "publishable": False,
    }
    evidence_path = root / "generated" / "credit-exhaustion-fallback.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")

    result = episode.render(root, "remotion", video=render)
    evidence["status"] = "rendered" if render else "ready_to_render"
    evidence["render"] = result
    evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "rendered" if render else "ready_to_render",
        "render": result,
        "runway_budget": budget,
        "provider_fallback": "definitive_runway_credit_exhaustion",
        "fallback_evidence": str(evidence_path),
        "publishable": False,
        "episode_dir": str(root),
    }


def run(draft_path, root, voice_id, avatar_id, live=False, render=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    board = build_board(draft)
    direction = visual_director.plan(draft["script"])
    visual_director.validate(direction)
    prompts = visual_prompts(direction)
    budget = enforce_runway_budget(board, len(prompts))
    (root / "storyboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")
    (root / "visual-direction.json").write_text(
        json.dumps(direction, indent=2) + "\n", encoding="utf-8")
    (root / "runway-budget.json").write_text(json.dumps(budget, indent=2) + "\n", encoding="utf-8")
    (root / "graphics.json").write_text(
        json.dumps({"headline": "UNREVIEWED SATOSHI PREVIEW"}, indent=2) + "\n", encoding="utf-8")
    if not live:
        audio = episode.submit_audio(root, voice_id, live=False)
        visuals = [episode.submit_visual(root, cue, prompt, live=False)
                   for cue, prompt in prompts]
        return {"status": "dry_run", "audio": audio, "visuals": visuals,
                "runway_budget": budget, "publishable": False, "episode_dir": str(root)}

    # A prior attempt may already have preserved the provider's definitive
    # no-credit rejection. Do not archive it and do not repeat the paid call.
    prior_credit_failure = _existing_credit_exhaustion(root)
    if prior_credit_failure:
        return _render_credit_fallback(
            root, board, prompts, direction, budget, render,
            trigger=prior_credit_failure)

    visual_results = []
    try:
        # Canary-first: prove one Gen-4.5 task can be created, completed and
        # collected before spending on narration, avatar, or five more visuals.
        # On a retry, submit_visual returns a durable existing record rather than
        # creating a replacement paid task.
        first_cue, first_prompt = prompts[0]
        canary = episode.submit_visual(root, first_cue, first_prompt, live=True)
        if not canary.get("record"):
            raise RuntimeError("Runway canary submission did not return a durable record")
        visual_results.append(
            _wait_record(root, canary["record"], episode.collect_visual))

        episode.submit_audio(root, voice_id, live=True)
        _wait_audio(root, voice_id)

        # Submit-and-collect sequentially. This prevents a downstream failure
        # from leaving multiple paid visual tasks in flight at once. Existing
        # records and collected outputs are reused after interruption.
        for cue, prompt in prompts[1:]:
            result = episode.submit_visual(root, cue, prompt, live=True)
            if not result.get("record"):
                raise RuntimeError("Visual submission did not return a durable record")
            visual_results.append(
                _wait_record(root, result["record"], episode.collect_visual))

        # A previously collected host plate is a reusable visual asset. Do not
        # spend again merely because the final edit follows a longer timeline.
        existing_host = root / "generated" / "host.mp4"
        if not existing_host.is_file():
            episode.narration(root)
            host = episode.submit_host(root, "avatar", live=True, avatar_id=avatar_id)
            if not host.get("record"):
                raise RuntimeError("Avatar submission did not return a durable record")
            _wait_record(root, host["record"], episode.collect_host)
    except Exception as exc:
        if not _provider_credit_exhausted(exc):
            raise
        return _render_credit_fallback(
            root, board, prompts, direction, budget, render,
            trigger={
                "provider_http_status": getattr(exc, "status_code", 400),
                "error_type": type(exc).__name__,
                "error": str(exc)[:2000],
            },
            completed_visuals=visual_results)

    plan = build_plan(root, board, visual_results, direction)
    (root / "footage-plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    result = episode.render(root, "remotion", video=render)
    return {"status": "rendered" if render else "ready_to_render",
            "render": result, "runway_budget": budget,
            "publishable": False, "episode_dir": str(root)}


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
