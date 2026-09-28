"""Persistent, bounded supervisor for the Satoshi preview pipeline.

Advances the first unmet stage, checkpoints state after every attempt, and reuses
cached provider/media outputs. It never publishes. Repeated identical failures
stop for human/code maintenance rather than hammering providers indefinitely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

STATE_VERSION = 1
DEFAULT_MODEL = "gpt-5.6-sol"
MAX_IDENTICAL_FAILURES = 3


def _read_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _fingerprint(stage: str, message: str) -> str:
    text = (stage + "\n" + message.strip())[-8000:]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]


def _request_id(request: dict) -> str:
    identity = {
        "topic": request.get("topic", ""),
        "angle": request.get("angle", ""),
        "model": DEFAULT_MODEL,
    }
    payload = json.dumps(identity, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _find_draft() -> Path | None:
    root = Path("outputs/satoshi-short/produce")
    if not root.exists():
        return None
    matches = sorted(root.rglob("draft.json"))
    return matches[0] if matches else None


def _state_path() -> Path:
    return Path(os.environ.get("SATOSHI_SUPERVISOR_STATE", "outputs/supervisor/state.json"))


def _blank_state(request_id=None):
    return {
        "schema_version": STATE_VERSION,
        "desired_state": "preview_rendered",
        "request_id": request_id,
        "attempts": {},
        "failure_fingerprint": None,
        "identical_failure_count": 0,
        "human_intervention_required": False,
        "current_state": "requested",
    }


def _load_state():
    path = _state_path()
    state = _read_json(path, {}) or {}
    base = _blank_state(state.get("request_id"))
    for key, value in base.items():
        state.setdefault(key, value)
    return state


def _save_state(state):
    state["updated_at_unix"] = int(time.time())
    _write_json(_state_path(), state)


def _run(stage: str, argv: list[str], state):
    state["current_stage"] = stage
    state["attempts"][stage] = int(state["attempts"].get(stage, 0)) + 1
    _save_state(state)
    proc = subprocess.run(argv, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout, end="")
    if proc.returncode == 0:
        state["failure_fingerprint"] = None
        state["identical_failure_count"] = 0
        state["last_error"] = None
        _save_state(state)
        return True
    message = (proc.stderr or proc.stdout or f"exit {proc.returncode}").strip()
    fp = _fingerprint(stage, message)
    if state.get("failure_fingerprint") == fp:
        state["identical_failure_count"] = int(state.get("identical_failure_count", 0)) + 1
    else:
        state["failure_fingerprint"] = fp
        state["identical_failure_count"] = 1
    state["last_error"] = message[-4000:]
    if state["identical_failure_count"] >= MAX_IDENTICAL_FAILURES:
        state["human_intervention_required"] = True
        state["current_state"] = "blocked_repeated_failure"
    _save_state(state)
    raise RuntimeError(f"{stage} failed [{fp}]: {message}")


def resolve_request(state):
    source = Path("requests/satoshi/current.json")
    if not source.exists():
        raise RuntimeError("requests/satoshi/current.json is missing")
    Path("outputs/chat-request").mkdir(parents=True, exist_ok=True)
    request = _read_json(source, {})
    request["model"] = DEFAULT_MODEL
    _write_json(Path("outputs/chat-request/request.json"), request)
    resolved = Path("outputs/chat-request/resolved.json")
    _run("resolve_request", [
        "python", "chat_request.py",
        "--input", "outputs/chat-request/request.json",
        "--output", str(resolved),
    ], state)
    return _read_json(resolved)


def ensure_request_identity(state, request):
    rid = _request_id(request)
    old = state.get("request_id")
    if old and old != rid:
        for path in (Path("outputs/satoshi-short"), Path("outputs/video-preview"), Path("remotion/out")):
            if path.exists():
                shutil.rmtree(path)
        fresh = _blank_state(rid)
        state.clear()
        state.update(fresh)
    else:
        state["request_id"] = rid
    _save_state(state)


def ensure_research(state, request):
    draft = _find_draft()
    if draft:
        state["current_state"] = "research_validated"
        state["research_draft"] = str(draft)
        _save_state(state)
        return draft

    # First try deterministic replay from a saved provider response. This bypasses
    # the paid-call reservation ledger and lets validator/code fixes reuse the
    # exact same Sol research output.
    replay = subprocess.run([
        "python", "satoshi_cached_replay.py",
        "--topic", request["topic"],
        "--angle", request.get("angle", ""),
        "--output", "outputs/satoshi-short",
        "--model", DEFAULT_MODEL,
    ], text=True, capture_output=True)
    if replay.stdout:
        print(replay.stdout, end="")
    if replay.returncode == 0:
        draft = _find_draft()
        if draft:
            state["current_state"] = "research_validated"
            state["research_draft"] = str(draft)
            state["last_error"] = None
            _save_state(state)
            return draft

    budget = str(request.get("max_openai_usd", 2.0))
    _run("research", [
        "python", "satoshi_short.py", "prepare",
        "--topic", request["topic"],
        "--angle", request.get("angle", ""),
        "--output", "outputs/satoshi-short",
        "--model", DEFAULT_MODEL,
        "--live",
        "--budget-usd", budget,
        "--max-usd-per-run", budget,
    ], state)
    draft = _find_draft()
    if not draft:
        raise RuntimeError("research succeeded but no draft.json was produced")
    state["current_state"] = "research_validated"
    state["research_draft"] = str(draft)
    _save_state(state)
    return draft


def ensure_media(state, draft: Path):
    final = Path("remotion/out/reel.mp4")
    if final.exists():
        state["current_state"] = "preview_rendered"
        state["final_mp4"] = str(final)
        _save_state(state)
        return final
    _run("runway_and_render", [
        "python", "unreviewed_video_preview.py",
        "--draft", str(draft),
        "--input-dir", "outputs/video-preview",
        "--voice-id", os.environ.get("RUNWAY_VOICE_PRESET", "vincent"),
        "--avatar-id", os.environ["RUNWAY_AVATAR_ID"],
        "--live", "--render",
    ], state)
    if not final.exists():
        raise RuntimeError("media stage completed without remotion/out/reel.mp4")
    state["current_state"] = "preview_rendered"
    state["final_mp4"] = str(final)
    _save_state(state)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status-only", action="store_true")
    args = parser.parse_args()
    state = _load_state()
    if args.status_only:
        print(json.dumps(state, indent=2, sort_keys=True))
        return
    try:
        request = resolve_request(state)
        ensure_request_identity(state, request)
        if state.get("human_intervention_required"):
            raise RuntimeError("paused after repeated identical failure")
        draft = ensure_research(state, request)
        final = ensure_media(state, draft)
        print(json.dumps({"status": "preview_rendered", "final_mp4": str(final)}, indent=2))
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"SUPERVISOR_BLOCKED: {exc}", file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
