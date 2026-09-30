"""Canonical Satoshi runtime with one continuous Runway host performance and distribution-aware publishing.

The underlying canonical runtime remains the story/production orchestrator. This
wrapper changes the final media handoff so the avatar is generated once against the
single concatenated narration master. That avoids segment-boundary drift from five
independently generated face clips. Remotion keeps the native Runway audio attached
to that continuous host, and every live render emits a distribution packet used by
Instagram.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import canonical_satoshi_runtime as base
import distribution_enrichment
import publish_satoshi_instagram
import release_instagram
import render_audio_guard
import runway_media

_ORIGINAL_PREPARE_REMOTION = base.prepare_remotion
_ORIGINAL_BUILD_STORY = base.build_story
_ORIGINAL_PERSIST_FINAL = base.persist_final
_ORIGINAL_ENSURE_HOST = base.ensure_host
_LAST_STORY = None


def _write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def ensure_continuous_host(root, board, request, live=False):
    """Generate exactly one avatar performance from the final narration master.

    The old canonical path generated five avatar clips and concatenated them. Even
    with native audio preserved, that introduced repeated segment boundaries and
    re-encoding opportunities for visible mouth/audio drift. Avatar mode now sends
    the single `generated/voice.wav` master to Runway once and uses the returned
    clip as the final host track. Non-avatar plate modes retain their existing path.
    """
    if request["host"]["mode"] != "avatar":
        return _ORIGINAL_ENSURE_HOST(root, board, request, live=live)
    if not live:
        return {"status": "dry_run", "mode": "avatar", "continuous": True}

    root = Path(root)
    avatar_id = (os.environ.get("RUNWAY_AVATAR_ID") or "").strip()
    if not avatar_id:
        raise ValueError("RUNWAY_AVATAR_ID is required for the moving host")

    narration = root / "generated" / "voice.wav"
    if not narration.is_file() or narration.stat().st_size <= 0:
        raise RuntimeError("Continuous avatar requires generated/voice.wav")

    target = root / "generated" / "host-continuous.mp4"
    ledger = root / "generated" / "runway-continuous"
    ledger.mkdir(parents=True, exist_ok=True)

    if not target.is_file() or target.stat().st_size <= 0:
        preview = runway_media.submit_avatar(avatar_id, narration, ledger, live=False)
        existing = base._existing_runway_record(ledger, preview["specification"])
        if existing:
            base._wait_collect(existing, target)
        else:
            submitted = runway_media.submit_avatar(avatar_id, narration, ledger, live=True)
            base._wait_collect(submitted["record"], target)

    # The host's own audio is the final playback authority. Require a usable stream
    # before spending anything on the Instagram stage.
    stats = render_audio_guard.validate(target)
    return {
        "status": "collected",
        "mode": "avatar",
        "continuous": True,
        "file": str(target),
        "audio_validation": stats,
    }


def prepare_remotion_native_audio(root, story, production, timing, stills, host_file, voice_file):
    """Package audit narration but tell Remotion to play host-native audio."""
    payload = _ORIGINAL_PREPARE_REMOTION(
        root, story, production, timing, stills, host_file, voice_file
    )
    payload["voice"] = ""
    Path("remotion/public/canonical-episode.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    Path(root, "remotion-episode.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def render_reel_native_audio():
    subprocess.run([
        "npx", "remotion", "render", "src/index.ts", "CanonicalSatoshiEpisode",
        "out/canonical-reel.mp4",
    ], cwd="remotion", check=True, timeout=1800)
    video = Path("remotion/out/canonical-reel.mp4")
    if not video.is_file() or video.stat().st_size <= 0:
        raise RuntimeError("Remotion did not produce canonical-reel.mp4")
    stats = render_audio_guard.validate(video)
    print(json.dumps({"continuous_native_host_audio": stats}, indent=2, sort_keys=True))
    return video


def build_story_capture(*args, **kwargs):
    global _LAST_STORY
    story = _ORIGINAL_BUILD_STORY(*args, **kwargs)
    _LAST_STORY = story
    return story


def persist_final_with_distribution(root, video, eid):
    """Generate distribution metadata after render/QC and before final persistence."""
    if _LAST_STORY is None:
        raise RuntimeError("Distribution enrichment missing final story")
    packet = distribution_enrichment.build(_LAST_STORY, live=True)
    packet["episode_id"] = eid
    _write_json(Path(root) / "distribution.json", packet)
    return _ORIGINAL_PERSIST_FINAL(root, video, eid)


def _assert_canonical_identity(root, story):
    """Fail closed if the publish directory does not match its copied request."""
    root = Path(root)
    request_path = root / "request.json"
    if not request_path.is_file():
        raise RuntimeError("Canonical publish missing request.json")
    request = json.loads(request_path.read_text(encoding="utf-8"))
    expected_episode_id = base.episode_id(request)
    if root.name != expected_episode_id:
        raise RuntimeError(
            f"Canonical request identity mismatch: root={root.name} expected={expected_episode_id}"
        )
    distribution_path = root / "distribution.json"
    if distribution_path.is_file():
        distribution = json.loads(distribution_path.read_text(encoding="utf-8"))
        packet_id = distribution.get("episode_id")
        if packet_id and packet_id != expected_episode_id:
            raise RuntimeError(
                f"Distribution identity mismatch: {packet_id} != {expected_episode_id}"
            )
    if not str(story.get("title") or "").strip():
        raise RuntimeError("Canonical publish has no final story title")
    return expected_episode_id


def publish_final_with_distribution(root, story, video, media_record):
    """Publish only the canonical request/story/distribution package for this episode."""
    _assert_canonical_identity(root, story)
    path = Path(root) / "distribution.json"
    if path.is_file():
        distribution = json.loads(path.read_text(encoding="utf-8"))
    else:
        distribution = distribution_enrichment.build(story, live=False)
        distribution["episode_id"] = Path(root).name
        _write_json(path, distribution)

    caption = str(distribution.get("caption") or story.get("title") or "Biotica").strip()[:2200]
    story_hash = hashlib.sha256(base._canonical(story).encode("utf-8")).hexdigest()
    release = release_instagram.build_release(
        str(video), media_record["url"], caption,
        "canonical-satoshi-distribution-runtime", story_hash, story_hash,
    )
    token = os.environ.get("META_ACCESS_TOKEN")
    user = os.environ.get("IG_USER_ID")
    if not token or not user:
        raise ValueError("META_ACCESS_TOKEN and IG_USER_ID required for Instagram publish")
    ledger = Path(root) / "instagram-posts.sqlite"
    result = publish_satoshi_instagram.publish(
        release, ledger, token, user, os.environ.get("META_GRAPH_VERSION", "v25.0")
    )
    packet = {
        "episode_id": Path(root).name,
        "release": release,
        "distribution": distribution,
        "result": result,
        "status": "published",
    }
    _write_json(Path(root) / "instagram.json", packet)
    return packet


def install_native_lipsync_overrides():
    base.ensure_host = ensure_continuous_host
    # Keep base._timing: overlays are timed to the exact narration segments that
    # were concatenated into voice.wav. Do not infer timings from re-encoded clips.
    base.prepare_remotion = prepare_remotion_native_audio
    base.render_reel = render_reel_native_audio
    base.build_story = build_story_capture
    base.persist_final = persist_final_with_distribution
    base.publish_final = publish_final_with_distribution


def main():
    install_native_lipsync_overrides()
    base.main()


if __name__ == "__main__":
    main()
