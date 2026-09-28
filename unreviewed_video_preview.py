"""Build an UNREVIEWED Satoshi video preview from a web-search draft.

This path is for production smoke tests only. It never marks claims reviewed or
content publishable. All inset media are Runway-generated illustrations. When a
durable Runway record proves the account cannot fund the visual canary, the
pipeline may render a clearly labelled graphics-only preview without making
additional provider calls.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import time
import wave
from pathlib import Path

import episode
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
GRAPHICS_ONLY_DURATION_SECONDS = 30
GRAPHICS_ONLY_FPS = 30


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


def _is_credit_rejection(value):
    """Recognize only explicit provider credit failures, never generic errors."""
    if isinstance(value, dict):
        status = value.get("provider_http_status")
        text = value.get("error", "")
    else:
        status = getattr(value, "status_code", None)
        text = str(value)
    normalized = str(text).casefold()
    return status in {400, 402, 403} and any(marker in normalized for marker in (
        "not have enough credits",
        "not enough credits",
        "insufficient credits",
    ))


def _credit_rejection_record(root, board, cue, prompt):
    """Find the exact durable canary rejection so retries make no provider call."""
    for path, data in _records(root, "visual"):
        spec = data.get("specification", {})
        if spec.get("cue_id") != cue or spec.get("prompt") != prompt or \
                spec.get("script_sha256") != board.get("script_sha256"):
            continue
        if data.get("state") == "rejected_no_task" and _is_credit_rejection(data):
            return path, data
    return None


def _caption_rows(board, words_per_caption=7):
    """Lay out the unreviewed script as deterministic on-screen captions."""
    chunks = []
    for cue in board.get("cues", []):
        words = cue.get("spoken_text", "").split()
        for index in range(0, len(words), words_per_caption):
            chunk = words[index:index + words_per_caption]
            if chunk:
                chunks.append(" ".join(chunk))
    total_words = sum(len(chunk.split()) for chunk in chunks)
    if total_words <= 0:
        raise ValueError("Graphics-only preview requires substantive script text")

    start_margin_ms = 500
    usable_ms = GRAPHICS_ONLY_DURATION_SECONDS * 1000 - 1000
    consumed = 0
    captions = []
    for text in chunks:
        count = len(text.split())
        start = start_margin_ms + round(usable_ms * consumed / total_words)
        consumed += count
        end = start_margin_ms + round(usable_ms * consumed / total_words)
        captions.append({
            "text": text,
            "startMs": start,
            "endMs": max(start + 1, end),
            "timestampMs": start,
            "confidence": None,
        })
    return captions


def _write_silent_narration(path):
    """Create a deterministic audio track so the rendered master is not muxed video-only."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    sample_rate = 48000
    frame_count = sample_rate * GRAPHICS_ONLY_DURATION_SECONDS
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        block = b"\x00\x00" * sample_rate
        for _ in range(GRAPHICS_ONLY_DURATION_SECONDS):
            output.writeframesraw(block)
        output.setnframes(frame_count)
    return path


def _render_graphics_only_preview(root, board, budget, rejection, render):
    """Render a truthful degraded preview after a definite no-task credit rejection.

    No provider media is fabricated or represented as generated footage. The
    output contains only the unreviewed script as typography, a persistent
    unreviewed label, and silence. The durable provider rejection remains in the
    Runway ledger and is referenced by the fallback manifest.
    """
    root = Path(root)
    remotion_root = Path("remotion")
    public = remotion_root / "public"
    public.mkdir(parents=True, exist_ok=True)

    narration = _write_silent_narration(root / "generated" / "narration.wav")
    public_audio = public / "generated" / "provider-unavailable-narration.wav"
    public_audio.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(narration, public_audio)

    record_path, record = rejection
    episode_data = {
        "plate": "",
        "plate_start_frames": 0,
        "loop_plate": False,
        "voice": "generated/provider-unavailable-narration.wav",
        "shots": [],
        "captions": _caption_rows(board),
        "duration_frames": GRAPHICS_ONLY_DURATION_SECONDS * GRAPHICS_ONLY_FPS,
        "fps": GRAPHICS_ONLY_FPS,
        "width": 1080,
        "height": 1920,
        "headline": "UNREVIEWED GRAPHICS-ONLY PREVIEW — PROVIDER MEDIA UNAVAILABLE",
        "fixture": False,
    }
    episode_path = public / "episode.json"
    episode_path.write_text(json.dumps(episode_data, indent=2) + "\n", encoding="utf-8")

    fallback = {
        "schema_version": 1,
        "status": "graphics_only_provider_credit_fallback",
        "script_sha256": board["script_sha256"],
        "provider_record": str(record_path),
        "provider_state": record.get("state"),
        "provider_http_status": record.get("provider_http_status"),
        "provider_error_type": record.get("error_type"),
        "media_mode": "typography_only",
        "audio_mode": "silence",
        "rights_status": "no_external_media_used",
        "review_status": "unreviewed_web_preview",
        "runway_budget": budget,
        "publishable": False,
    }
    fallback_path = root / "graphics-only-preview.json"
    fallback_path.write_text(json.dumps(fallback, indent=2) + "\n", encoding="utf-8")

    final = remotion_root / "out" / "reel.mp4"
    if render:
        final.unlink(missing_ok=True)
        proc = subprocess.run(["npm", "run", "render"], cwd=remotion_root, text=True)
        if proc.returncode != 0:
            raise RuntimeError(
                f"Graphics-only Remotion render failed with exit {proc.returncode}")
        if not final.is_file() or final.stat().st_size <= 0:
            raise RuntimeError("Graphics-only render completed without remotion/out/reel.mp4")

    return {
        "status": "rendered_graphics_only" if render else "ready_to_render_graphics_only",
        "render": {
            "manifest": str(fallback_path),
            "video": str(final) if render else None,
            "publishable": False,
        },
        "runway_budget": budget,
        "provider_calls_after_rejection": 0,
        "publishable": False,
        "episode_dir": str(root),
    }


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

    # Canary-first: prove one Gen-4.5 task can be created, completed and collected
    # before spending on narration, avatar, or five additional visual jobs. A
    # durable credit rejection is consumed as evidence and never retried; the
    # result is instead a clearly labelled graphics-only unreviewed preview.
    first_cue, first_prompt = prompts[0]
    prior_credit_rejection = _credit_rejection_record(
        root, board, first_cue, first_prompt)
    if prior_credit_rejection:
        return _render_graphics_only_preview(
            root, board, budget, prior_credit_rejection, render)

    try:
        canary = episode.submit_visual(root, first_cue, first_prompt, live=True)
    except Exception as exc:
        if not _is_credit_rejection(exc):
            raise
        rejection = _credit_rejection_record(root, board, first_cue, first_prompt)
        if not rejection:
            raise RuntimeError(
                "Runway reported insufficient credits without writing a durable rejection record") from exc
        return _render_graphics_only_preview(root, board, budget, rejection, render)

    if canary.get("state") == "rejected_no_task":
        rejection = _credit_rejection_record(root, board, first_cue, first_prompt)
        if rejection:
            return _render_graphics_only_preview(root, board, budget, rejection, render)
    if not canary.get("record"):
        raise RuntimeError("Runway canary submission did not return a durable record")
    visual_results = [_wait_record(root, canary["record"], episode.collect_visual)]

    episode.submit_audio(root, voice_id, live=True)
    _wait_audio(root, voice_id)

    # Submit-and-collect sequentially. This prevents a downstream failure from
    # leaving multiple paid visual tasks in flight at once. Existing records and
    # locally collected outputs are deterministically reused after interruption.
    for cue, prompt in prompts[1:]:
        result = episode.submit_visual(root, cue, prompt, live=True)
        if not result.get("record"):
            raise RuntimeError("Visual submission did not return a durable record")
        visual_results.append(_wait_record(root, result["record"], episode.collect_visual))

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
