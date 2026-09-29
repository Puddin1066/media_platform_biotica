"""Single-entry media stage for conversational Satoshi shorts.

Pre-seeds canonical narration through the selected speech provider, then delegates
visual generation, host performance and deterministic assembly to the existing
preview pipeline. Existing audio files make the Runway TTS stage a no-op, so the
same narration bytes drive host generation and the final mix.

Host modes:
  - avatar: default Runway custom avatar (driver appears on camera)
  - uploaded_plate: your filmed plate is the on-camera body; RUNWAY_AVATAR_ID is
    only an internal speech/performance driver via Act Two

Visual modes (SATOSHI_VISUAL_MODE / --visual-mode):
  - lean (default): Commons stills for insets; Runway for host only
  - ai: six Gen-4.5 illustrative insets (legacy high-spend path)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import episode
import plate_host
import speech_provider
import unreviewed_video_preview as preview


def run(draft_path, root, voice_id, avatar_id, live=False, render=False,
        host_mode="avatar", plate_local_path=None, plate_r2_key=None,
        visual_mode=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if host_mode not in {"avatar", "uploaded_plate"}:
        raise ValueError("host_mode must be avatar or uploaded_plate")
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    board = preview.build_board(draft)
    (root / "storyboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")

    speech = speech_provider.generate_episode_audio(root, board, live=live)
    originals = None
    try:
        if host_mode == "uploaded_plate":
            originals = plate_host.install_uploaded_plate_host(
                root, plate_local_path, avatar_id, live=live,
                plate_r2_key=plate_r2_key or os.environ.get("SATOSHI_PLATE_R2_KEY"),
            )
        result = preview.run(
            draft_path, root, voice_id, avatar_id, live=live, render=render,
            visual_mode=visual_mode)
    finally:
        if originals:
            episode.submit_host, episode.collect_host = originals
    result["speech_provider"] = speech_provider.selected_provider()
    result["speech"] = speech
    result["host_mode"] = host_mode
    result["visual_mode"] = result.get("visual_mode") or preview.resolve_visual_mode(visual_mode)
    if plate_local_path:
        result["plate_local_path"] = str(plate_local_path)
    if plate_r2_key or os.environ.get("SATOSHI_PLATE_R2_KEY"):
        result["plate_r2_key"] = plate_r2_key or os.environ.get("SATOSHI_PLATE_R2_KEY")
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft", required=True)
    p.add_argument("--input-dir", default="outputs/video-preview")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--avatar-id", required=True,
                   help="Visible avatar, or internal driver when --host-mode uploaded_plate")
    p.add_argument("--host-mode", choices=("avatar", "uploaded_plate"), default="avatar")
    p.add_argument("--visual-mode", choices=preview.VISUAL_MODES, default=None,
                   help="lean=Commons insets (default); ai=Gen-4.5 insets")
    p.add_argument("--plate-local-path", help="Local MOV/MP4 filmed plate")
    p.add_argument("--plate-r2-key", default=os.environ.get("SATOSHI_PLATE_R2_KEY"),
                   help="R2 object key for the filmed plate")
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(
            args.draft, args.input_dir, args.voice_id, args.avatar_id,
            live=args.live, render=args.render, host_mode=args.host_mode,
            plate_local_path=args.plate_local_path, plate_r2_key=args.plate_r2_key,
            visual_mode=args.visual_mode,
        ), indent=2))
    except (ValueError, OSError, RuntimeError, TimeoutError, KeyError, TypeError) as exc:
        p.exit(1, "Singular video preview blocked: %s\n" % exc)


if __name__ == "__main__":
    main()
