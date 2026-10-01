"""Provider-free smoke fixture for the current canonical Studio composition.

Synthetic background and a test tone exercise the real renderer/audio guard.
They are test inputs, not an example episode or a lip-sync quality assessment.
Run in a disposable CI checkout: this replaces canonical-episode.json there.
"""
import json
import subprocess
from pathlib import Path

import narration_alignment
import studio_media


def main():
    assets = Path("remotion/public/canonical-assets")
    assets.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=0x28374b:s=360x640:d=3",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(assets / "host.mp4")], check=True)
    raw = assets / "test-tone.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=250:duration=3",
                    "-ar", "48000", "-ac", "2", str(raw)], check=True)
    studio_media.mix_audio(raw, assets / "voice.wav", 3000, [400])
    script = {"script": [{"sentence_id": "s01", "text": "Evidence deserves a closer look today."}]}
    words = [{"word": word, "start": i * .4, "end": i * .4 + .3}
             for i, word in enumerate("Evidence deserves a closer look today".split())]
    captions = narration_alignment.align_words(script, words, 3000, "synthetic")["captions"]
    payload = {"title": "Synthetic layout test", "host": "canonical-assets/host.mp4", "voice": "canonical-assets/voice.wav",
               "fps": 30, "width": 1080, "height": 1920, "duration_frames": 90, "captions": captions,
               "beats": [{"beat_id": "test", "role": "typography", "text": "", "citations": [], "still": "",
                          "motion": "hold", "from": 0, "duration": 90, "visual_type": "typography",
                          "screen_text": "A mechanism is not a treatment", "source_label": "SYNTHETIC LAYOUT TEST"}]}
    Path("remotion/public/canonical-episode.json").write_text(json.dumps(payload))


if __name__ == "__main__":
    main()
