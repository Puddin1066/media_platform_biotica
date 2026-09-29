"""Tests for OpenAI still inset path (default Satoshi visual mode)."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import openai_stills
import unreviewed_video_preview as uvp
import visual_director

from test_lean_visuals import LeanVisualsTests


class OpenAIStillTests(unittest.TestCase):
    def draft(self):
        return LeanVisualsTests().draft()

    def test_default_visual_mode_is_stills(self):
        self.assertEqual(uvp.DEFAULT_VISUAL_MODE, "stills")
        with patch.dict("os.environ", {"SATOSHI_VISUAL_MODE": ""}, clear=False):
            # Empty env falls through to DEFAULT_VISUAL_MODE.
            self.assertEqual(uvp.resolve_visual_mode(""), "stills")
        self.assertEqual(uvp.resolve_visual_mode("stills"), "stills")

    def test_prompt_is_topic_still_not_runway_video_spec(self):
        slot = {"visual_function": "pattern_interrupt", "overlay_text": "IGNORED"}
        prompt = openai_stills.prompt_for_slot(slot, "Haemanthus Raman PCR fingerstick")
        self.assertIn("fingerstick", prompt.casefold())
        self.assertIn("Haemanthus", prompt)
        self.assertNotIn("IGNORED", prompt)
        self.assertIn("picture-in-picture", prompt)

    def test_dry_collect_returns_six_openai_placeholders(self):
        draft = self.draft()
        direction = visual_director.plan(draft["script"])
        with tempfile.TemporaryDirectory() as d:
            rows = openai_stills.collect_openai_stills(
                d, direction, draft_topic=draft["case"]["question"], live=False)
        self.assertEqual(len(rows), 6)
        self.assertEqual(rows[0]["candidate"]["provider"], "openai")
        self.assertEqual(rows[0]["state"], "dry_run")

    def test_build_plan_openai_selection_basis(self):
        draft = self.draft()
        board = uvp.build_board(draft)
        direction = visual_director.plan(draft["script"])
        with tempfile.TemporaryDirectory() as d:
            rows = openai_stills.collect_openai_stills(
                d, direction, draft_topic=board["topic"], live=False)
            plan = uvp.build_plan(d, board, rows, direction)
        self.assertEqual(plan["shots"][0]["provider"], "openai")
        self.assertEqual(plan["shots"][0]["selection_basis"], "openai_still_topic_visuals")
        self.assertEqual(plan["shots"][0]["credit"], "AI-GENERATED STILL (DRY RUN)")

    def test_stills_budget_skips_gen45_visual_credits(self):
        board = uvp.build_board(self.draft())
        estimate = uvp.estimated_runway_credits(board, visual_count=0, visual_mode="stills")
        self.assertEqual(estimate["visuals"], 0)
        self.assertEqual(estimate["visual_mode"], "stills")

    def test_stills_dry_run_does_not_call_runway_visuals(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            draft.write_text(json.dumps(self.draft()))
            with patch.dict("os.environ", {"SATOSHI_VISUAL_MODE": "stills"}, clear=False), \
                 patch("unreviewed_video_preview.episode.submit_audio",
                       return_value={"opening": {"state": "dry_run"}}) as audio, \
                 patch("unreviewed_video_preview.episode.submit_visual") as visual:
                result = uvp.run(draft, Path(d) / "episode", "voice", "avatar")
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(result["visual_mode"], "stills")
            self.assertEqual(result["runway_budget"]["visuals"], 0)
            self.assertEqual(len(result["visuals"]), 6)
            self.assertEqual(result["visuals"][0]["candidate"]["provider"], "openai")
            visual.assert_not_called()
            audio.assert_called_once()

    def test_live_collect_writes_mp4_from_mocked_image_bytes(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg required")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            # Seed a tiny PNG via ffmpeg for the mock generator.
            seed = root / "seed.png"
            subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64",
                 "-frames:v", "1", str(seed)],
                check=True, capture_output=True)
            png = seed.read_bytes()
            direction = visual_director.plan(self.draft()["script"])

            def fake_generate(prompt, **_kwargs):
                self.assertIn("Photoreal", prompt)
                return png

            rows = openai_stills.collect_openai_stills(
                root, direction, draft_topic="Haemanthus", live=True,
                generate=fake_generate)
            self.assertEqual(len(rows), 6)
            for row in rows:
                media = root / row["candidate"]["media_source"]
                self.assertTrue(media.is_file())
                self.assertGreater(media.stat().st_size, 0)
                self.assertEqual(row["candidate"]["provider"], "openai")


class SupervisorStillsIdentityTests(unittest.TestCase):
    def test_request_identity_changes_stills_vs_lean(self):
        import satoshi_supervisor
        request = {"topic": "TRT", "angle": "x", "visual_mode": "stills"}
        with patch("satoshi_supervisor.writing_contract.digest", return_value="a" * 64):
            stills = satoshi_supervisor._request_id(request)
            lean = satoshi_supervisor._request_id({**request, "visual_mode": "lean"})
        self.assertNotEqual(stills, lean)


if __name__ == "__main__":
    unittest.main()
