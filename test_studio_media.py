"""Contract tests for the active Studio graph and executable production handoff."""
import importlib.util
import json
import tempfile
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import narration_alignment as alignment
import satoshi_editorial_pipeline as editorial
import studio_media as media

spec = importlib.util.spec_from_file_location("current_studio_runner", "studio/module_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class StudioMediaTests(unittest.TestCase):
    def script(self):
        return {"title": "Evidence", "script": [
            {"sentence_id": "s01", "text": "The finding matters."},
            {"sentence_id": "s02", "text": "Here is why."}]}

    def timing(self, sha="voice"):
        words = [{"word": w, "start": i * .4, "end": i * .4 + .3}
                 for i, w in enumerate("The finding matters Here is why".split())]
        timing = alignment.align_words(self.script(), words, 3000, sha)
        timing["script_sha256"] = editorial.sha(self.script())
        return timing

    def test_measured_captions_preserve_script_words_and_pauses(self):
        timing = self.timing()
        self.assertAlmostEqual(timing["sentences"][1]["startMs"], 1200)
        self.assertEqual(timing["captions"][2]["text"], " matters.")
        self.assertTrue(timing["captions"][2]["pageBreakAfter"])

    def test_transcription_cannot_change_claim(self):
        with self.assertRaisesRegex(ValueError, "differs"):
            alignment.align_words(self.script(), [{"word": "Invented", "start": 0, "end": 1}], 3000, "x")

    def test_reject_nonfinite_overlapping_and_out_of_range_times(self):
        for bad in [float("nan"), -1, 10]:
            words = [{"word": w, "start": i * .4, "end": i * .4 + .3}
                     for i, w in enumerate("The finding matters Here is why".split())]
            words[0]["start"] = bad
            with self.assertRaises(ValueError):
                alignment.align_words(self.script(), words, 3000, "x")

    def test_plan_must_cover_current_script_exactly(self):
        shots = [{"shot_id": "one", "sentence_ids": ["s01"]}]
        with self.assertRaisesRegex(ValueError, "every"):
            media.compile_shots(self.script(), {"shots": shots})
        shots += [{"shot_id": "two", "sentence_ids": ["s01", "s02"]}]
        with self.assertRaisesRegex(ValueError, "overlap"):
            media.compile_shots(self.script(), {"shots": shots})

    def test_speech_segments_use_measured_boundaries_not_word_counts(self):
        timing = {"duration_ms": 61000, "sentences": [{"startMs": x} for x in (0, 12000, 28000, 42000, 56000)]}
        self.assertEqual(media.host_segments(timing), [(0, 28000), (28000, 56000), (56000, 61000)])
        with self.assertRaisesRegex(ValueError, "boundary"):
            media.host_segments({"duration_ms": 60000, "sentences": [{"startMs": 0}]})

    def test_changed_audio_marks_host_alignment_assembly_publish_stale(self):
        registry = json.loads(Path("studio/modules.json").read_text())
        manifest = {"modules": {m["id"]: {"status": "completed", "version": 1} for m in registry["modules"]}}
        with tempfile.TemporaryDirectory() as tmp, patch.object(runner, "ROOT", Path(tmp)):
            media.write(Path(tmp) / "studio/modules.json", registry)
            runner.complete("test-episode", manifest, "audio_review", ["new_audio.json"])
        for module in ("alignment", "host", "assembly", "publish"):
            self.assertEqual(manifest["modules"][module]["status"], "stale")
        self.assertEqual(manifest["modules"]["assets"]["status"], "completed")

    def test_publish_stops_before_provider_when_assembly_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts, _ = media.paths(tmp, "test-episode")
            media.write(artifacts / "assembly_manifest.json", {"script_sha256": "old"})
            media.write(artifacts / "canonical_script.json", self.script())
            media.write(artifacts / "audio_evaluation.json", {"selected_audio": {"sha256": "voice"}})
            for name in ("narration_alignment", "assets_manifest", "host_manifest", "visual_plan"):
                media.write(artifacts / (name + ".json"), {})
            with patch.object(media.lipsync, "publish_final_with_distribution") as publish:
                with self.assertRaisesRegex(ValueError, "stale"):
                    media.run_publish(tmp, "test-episode", {}, "")
                publish.assert_not_called()

    def test_assembly_consumes_all_artifacts_and_keeps_mix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifacts, work = media.paths(root, "test-episode")
            script, timing = self.script(), self.timing()
            plan = {"shots": [{"shot_id": "one", "type": "typography", "sentence_ids": ["s01", "s02"], "screen_text": "A receipt"}]}
            assets = {"script_sha256": editorial.sha(script), "visual_plan_sha256": editorial.sha(plan),
                      "shots": [{**plan["shots"][0], "visual_type": "typography"}]}
            for name, value in [("canonical_script", script), ("narration_alignment", timing), ("visual_plan", plan),
                                ("assets_manifest", assets), ("host_manifest", {"plate": {"key": "plate"}, "loop": True, "lip_sync": "not_applied"})]:
                media.write(artifacts / (name + ".json"), value)
            voice = root / "voice.wav"; voice.write_bytes(b"locked")
            video = root / "final.mp4"; video.write_bytes(b"rendered")
            def fetch(key, path):
                Path(path).parent.mkdir(parents=True, exist_ok=True); Path(path).write_bytes(b"plate")
            def mix(audio, output, duration, cues):
                output.parent.mkdir(parents=True, exist_ok=True); output.write_bytes(b"voice-and-effects");return output
            with patch.object(media, "selected_audio", return_value=(voice, {"sha256": "voice"})), \
                 patch.object(media.media_store, "fetch", side_effect=fetch), \
                 patch.object(media, "mix_audio", side_effect=mix), \
                 patch.object(media.production, "render_reel", return_value=video), \
                 patch.object(media.media_store, "persist", return_value={"key": "final", "url": "https://media.example/final.mp4"}):
                media.run_assembly(root, "test-episode", {}, "")
            payload = media.read(root / "remotion/public/canonical-episode.json")
            self.assertEqual(payload["captions"], timing["captions"])
            self.assertEqual((root / "remotion/public/canonical-assets/voice.wav").read_bytes(), b"voice-and-effects")
            self.assertEqual(payload["duration_frames"], 90)
            self.assertTrue(payload["loop_host"])
            manifest = media.read(artifacts / "assembly_manifest.json")
            self.assertEqual(manifest["audio_sha256"], "voice")
            self.assertEqual(manifest["status"], "rendered_requires_review")

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg not installed")
    def test_real_mix_preserves_narration_and_survives_audio_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            voice, mixed, video = root / "voice.wav", root / "mixed.wav", root / "final.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=250:duration=3",
                            "-ar", "48000", "-ac", "2", str(voice)], check=True)
            original = alignment.file_sha(voice)
            media.mix_audio(voice, mixed, 3000, [500, 1500])
            self.assertEqual(alignment.file_sha(voice), original)
            self.assertNotEqual(alignment.file_sha(mixed), original)
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=180x320:d=3",
                            "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)], check=True)
            result = media.render_audio_guard.mux_master_narration(video, mixed)
            self.assertEqual(result["sample_rate"], 48000)
            self.assertEqual(result["channels"], 2)
            self.assertAlmostEqual(result["video_seconds"], 3, places=1)

    def test_every_registered_module_has_real_runner(self):
        modules = json.loads(Path("studio/modules.json").read_text())["modules"]
        self.assertEqual({m["id"] for m in modules}, set(runner.RUNNERS))


if __name__ == "__main__":
    unittest.main()
