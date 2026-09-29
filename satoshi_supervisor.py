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

import writing_contract

STATE_VERSION = 2
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


def _request_id(request: dict, contract_hash: str | None = None) -> str:
    contract_hash = contract_hash or writing_contract.digest()
    identity = {
        "topic": request.get("topic", ""),
        "angle": request.get("angle", ""),
        "model": DEFAULT_MODEL,
        "writing_contract_hash": contract_hash,
        # Media identity: changing stills/lean/ai or host plate must invalidate caches.
        "host_mode": request.get("host_mode", "avatar"),
        "plate_r2_key": request.get("plate_r2_key", ""),
        "visual_mode": request.get("visual_mode", "stills"),
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


def _blank_state(request_id=None, contract_hash=None):
    return {
        "schema_version": STATE_VERSION,
        "desired_state": "preview_rendered",
        "request_id": request_id,
        "writing_contract_hash": contract_hash,
        "attempts": {},
        "failure_fingerprint": None,
        "identical_failure_count": 0,
        "human_intervention_required": False,
        "current_state": "requested",
    }


def _load_state():
    path = _state_path()
    state = _read_json(path, {}) or {}
    base = _blank_state(state.get("request_id"), state.get("writing_contract_hash"))
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
    contract_hash = writing_contract.digest()
    rid = _request_id(request, contract_hash)
    old = state.get("request_id")
    old_contract = state.get("writing_contract_hash")
    if old and (old != rid or old_contract != contract_hash):
        for path in (Path("outputs/satoshi-short"), Path("outputs/video-preview"), Path("remotion/out")):
            if path.exists():
                shutil.rmtree(path)
        fresh = _blank_state(rid, contract_hash)
        state.clear()
        state.update(fresh)
    else:
        state["request_id"] = rid
        state["writing_contract_hash"] = contract_hash
        state["schema_version"] = STATE_VERSION
    _save_state(state)


def ensure_research(state, request):
    draft = _find_draft()
    if draft:
        state["current_state"] = "research_validated"
        state["research_draft"] = str(draft)
        _save_state(state)
        return draft

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


def _runway_voice_preset():
    voice = os.environ.get("RUNWAY_VOICE_PRESET", "Vincent").strip()
    if voice.casefold() == "vincent":
        return "Vincent"
    return voice


def _preview_command(draft: Path, host_mode: str, plate_local=None, plate_r2=None,
                     visual_mode=None):
    cmd = [
        "python", "singular_video_preview.py",
        "--draft", str(draft),
        "--input-dir", "outputs/video-preview",
        "--voice-id", _runway_voice_preset(),
        "--avatar-id", os.environ["RUNWAY_AVATAR_ID"],
        "--host-mode", host_mode,
        "--live", "--render",
    ]
    if visual_mode:
        cmd.extend(["--visual-mode", visual_mode])
    if host_mode == "uploaded_plate":
        if plate_local:
            cmd.extend(["--plate-local-path", plate_local])
        if plate_r2:
            cmd.extend(["--plate-r2-key", plate_r2])
    return cmd


def _definite_uploaded_plate_not_found(message):
    """Recognize only the explicit object-store miss safe for preview fallback."""
    text = str(message or "").casefold()
    has_404 = "(404)" in text or "status code: 404" in text or "statuscode=404" in text
    return "headobject" in text and has_404 and "not found" in text


def _record_uploaded_plate_fallback(state, plate_r2):
    """Preserve failure evidence while allowing a nonpublishable avatar preview."""
    state["host_fallback"] = {
        "requested_host_mode": "uploaded_plate",
        "effective_host_mode": "avatar",
        "reason": "requested R2 plate returned a definitive HeadObject 404",
        "missing_r2_key": plate_r2,
        "observed_failure_fingerprint": state.get("failure_fingerprint"),
        "observed_error": state.get("last_error"),
        "scope": "UNREVIEWED_PREVIEW_ONLY",
        "publishable": False,
    }
    state["uploaded_plate_not_found_key"] = plate_r2
    state["human_intervention_required"] = False
    state["failure_fingerprint"] = None
    state["identical_failure_count"] = 0
    state["current_state"] = "research_validated"
    _save_state(state)


def ensure_media(state, draft: Path, request: dict | None = None):
    request = request or {}
    final = Path("remotion/out/reel.mp4")
    requested_host_mode = request.get("host_mode") or os.environ.get("SATOSHI_HOST_MODE", "avatar")
    visual_mode = str(request.get("visual_mode") or os.environ.get("SATOSHI_VISUAL_MODE") or "stills").strip().casefold()
    if visual_mode not in {"stills", "lean", "ai"}:
        raise ValueError("visual_mode must be stills, lean, or ai")
    if final.exists():
        narration = Path("outputs/video-preview/generated/narration.wav")
        if not narration.exists():
            raise RuntimeError("cached preview is missing generated/narration.wav")
        _run("validate_cached_master_audio", [
            "python", "render_audio_guard.py",
            "--video", str(final),
            "--narration", str(narration),
        ], state)
        state["current_state"] = "preview_rendered"
        state["final_mp4"] = str(final)
        state.setdefault("requested_host_mode", requested_host_mode)
        state.setdefault("effective_host_mode", state.get("host_mode", requested_host_mode))
        state.setdefault("visual_mode", visual_mode)
        _save_state(state)
        return final

    plate_local = request.get("plate_local_path") or os.environ.get("SATOSHI_PLATE_LOCAL_PATH")
    plate_r2 = request.get("plate_r2_key") or os.environ.get("SATOSHI_PLATE_R2_KEY")
    effective_host_mode = requested_host_mode

    # Once this exact remote key has produced an explicit HeadObject 404, do not
    # repeatedly query it. A newly supplied local plate always takes precedence.
    if requested_host_mode == "uploaded_plate" and not plate_local and plate_r2 and \
            state.get("uploaded_plate_not_found_key") == plate_r2:
        effective_host_mode = "avatar"

    if effective_host_mode == "uploaded_plate":
        try:
            _run(
                "speech_visuals_host_and_render",
                _preview_command(draft, effective_host_mode, plate_local, plate_r2,
                                 visual_mode=visual_mode),
                state,
            )
        except RuntimeError:
            # A missing optional filmed plate must not cause repeated metadata
            # fetches or discard already collected narration/visual tasks. The
            # fallback is limited to an explicitly unreviewed, nonpublishable
            # preview and uses the already configured avatar path.
            if plate_local or not plate_r2 or not _definite_uploaded_plate_not_found(
                    state.get("last_error")):
                raise
            _record_uploaded_plate_fallback(state, plate_r2)
            effective_host_mode = "avatar"
            _run(
                "speech_visuals_avatar_fallback_and_render",
                _preview_command(draft, effective_host_mode, visual_mode=visual_mode),
                state,
            )
    else:
        stage = ("speech_visuals_avatar_fallback_and_render"
                 if requested_host_mode == "uploaded_plate"
                 else "speech_visuals_host_and_render")
        _run(stage, _preview_command(draft, effective_host_mode,
                                     visual_mode=visual_mode), state)

    if not final.exists():
        raise RuntimeError("media stage completed without remotion/out/reel.mp4")
    state["current_state"] = "preview_rendered"
    state["final_mp4"] = str(final)
    state["requested_host_mode"] = requested_host_mode
    state["effective_host_mode"] = effective_host_mode
    state["host_mode"] = effective_host_mode
    state["visual_mode"] = visual_mode
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
        final = ensure_media(state, draft, request)
        print(json.dumps({
            "status": "preview_rendered",
            "final_mp4": str(final),
            "requested_host_mode": state.get(
                "requested_host_mode", request.get("host_mode", "avatar")),
            "host_mode": state.get(
                "effective_host_mode", request.get("host_mode", "avatar")),
            "visual_mode": state.get("visual_mode", request.get("visual_mode", "stills")),
            "publishable": False,
        }, indent=2))
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        print(f"SUPERVISOR_BLOCKED: {exc}", file=os.sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
