"""Canonical Satoshi runtime with continuous host performance, custom narration, and distribution-aware publishing.

The underlying canonical runtime remains the story/production orchestrator. This
wrapper makes three production guarantees: narration comes from the canonical
speech provider rather than a silent Vincent fallback; the avatar is generated
once against the single concatenated narration master; and every live render
emits a distribution packet used by Instagram.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import canonical_satoshi_runtime as base
import distribution_enrichment
import media_store
import plate_host
import publish_satoshi_instagram
import release_instagram
import render_audio_guard
import runway_media
import speech_provider

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


def ensure_canonical_audio(root, board, live=False):
    """Generate narration with the explicitly selected canonical speech provider.

    OpenAI is the canonical default. Runway TTS remains available only when
    deliberately selected; there is no implicit Vincent fallback in this wrapper.
    """
    provider = speech_provider.selected_provider()
    if provider in {"openai", "elevenlabs"}:
        result = speech_provider.generate_episode_audio(root, board, live=live)
        return {"provider": provider, "result": result}
    if provider == "runway":
        voice = (os.environ.get("RUNWAY_VOICE_PRESET") or "").strip()
        if not voice or voice.lower() == "vincent":
            raise ValueError(
                "Canonical Satoshi may not silently use the Vincent Runway preset; choose OpenAI narration or configure a deliberate non-Vincent Runway voice"
            )
        return base.ensure_audio(root, board, live=live)
    raise ValueError(f"Unsupported canonical Satoshi speech provider: {provider}")


def _configured_plate_key(host):
    return str(
        host.get("r2_key")
        or os.environ.get("SATOSHI_MASTER_HOST_R2_KEY")
        or os.environ.get("SATOSHI_DEFAULT_PLATE_R2_KEY")
        or os.environ.get("SATOSHI_PLATE_R2_KEY")
        or ""
    ).strip()


def _master_host_request(request):
    """Resolve a reusable plate. An empty key selects one already stored in R2.

    Explicit request or repository keys still win. Otherwise Pipeline B uses
    whatever video objects are already under satoshi/plates/ so a new episode
    does not require a freshly generated host file.
    """
    host = dict(request.get("host") or {})
    if host.get("mode") != "master_asset":
        return request
    key = _configured_plate_key(host)
    if not key:
        available = media_store.available_plates()
        chosen = media_store.select_plate(
            available, json.dumps(request, sort_keys=True, default=str))
        key = chosen["key"]
    resolved = dict(request)
    resolved["host"] = {"mode": "r2_plate", "r2_key": key}
    return resolved


def reuse_existing_plate(root, key):
    """Download one stored plate and use it as the host picture.

    Runway is not called. New narration is mixed later; the plate file itself
    is not regenerated.
    """
    root = Path(root)
    destination = root / "generated" / "host-plate.mp4"
    suffix = Path(key).suffix.lower()
    source = destination if suffix == ".mp4" else root / "generated" / f"host-plate-source{suffix}"
    media_store.fetch(key, source)
    return plate_host.ensure_local_mp4_plate(source, destination)


def ensure_continuous_host(root, board, request, live=False):
    """Use a stored plate, or generate one continuous avatar when no plate is requested."""
    mode = request["host"]["mode"]
    if mode == "master_asset":
        if not live:
            return {"status": "dry_run", "mode": "master_asset", "reusable": True, "generated": False}
        resolved = _master_host_request(request)
        key = resolved["host"]["r2_key"]
        destination = reuse_existing_plate(root, key)
        return {
            "status": "reused",
            "mode": "master_asset",
            "reusable": True,
            "generated": False,
            "file": str(destination),
            "plate_key": key,
        }
    if mode != "avatar":
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

    stats = render_audio_guard.validate(target)
    return {
        "status": "collected",
        "mode": "avatar",
        "continuous": True,
        "file": str(target),
        "audio_validation": stats,
    }


def prepare_remotion_native_audio(root, story, production, timing, stills, host_file, voice_file):
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
    if _LAST_STORY is None:
        raise RuntimeError("Distribution enrichment missing final story")
    packet = distribution_enrichment.build(_LAST_STORY, live=True)
    packet["episode_id"] = eid
    _write_json(Path(root) / "distribution.json", packet)
    return _ORIGINAL_PERSIST_FINAL(root, video, eid)


def _assert_canonical_identity(root, story):
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
    base.ensure_audio = ensure_canonical_audio
    base.ensure_host = ensure_continuous_host
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
