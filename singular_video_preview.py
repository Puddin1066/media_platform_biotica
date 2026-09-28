"""Single-entry media stage for conversational Satoshi shorts.

Pre-seeds canonical narration through the selected speech provider, then delegates
visual generation, host performance and deterministic assembly to the existing
preview pipeline. Existing audio files make the Runway TTS stage a no-op, so the
same narration bytes drive host generation and the final mix.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import speech_provider
import unreviewed_video_preview as preview


def run(draft_path, root, voice_id, avatar_id, live=False, render=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    draft = json.loads(Path(draft_path).read_text(encoding="utf-8"))
    board = preview.build_board(draft)
    (root / "storyboard.json").write_text(json.dumps(board, indent=2) + "\n", encoding="utf-8")

    speech = speech_provider.generate_episode_audio(root, board, live=live)
    result = preview.run(draft_path, root, voice_id, avatar_id, live=live, render=render)
    result["speech_provider"] = speech_provider.selected_provider()
    result["speech"] = speech
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--draft", required=True)
    p.add_argument("--input-dir", default="outputs/video-preview")
    p.add_argument("--voice-id", required=True)
    p.add_argument("--avatar-id", required=True)
    p.add_argument("--live", action="store_true")
    p.add_argument("--render", action="store_true")
    args = p.parse_args()
    try:
        print(json.dumps(run(args.draft, args.input_dir, args.voice_id, args.avatar_id,
                             live=args.live, render=args.render), indent=2))
    except (ValueError, OSError, RuntimeError, TimeoutError, KeyError, TypeError) as exc:
        p.exit(1, "Singular video preview blocked: %s\n" % exc)


if __name__ == "__main__":
    main()
