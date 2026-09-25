import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import unreviewed_video_preview as uvp

class PreviewVideoTests(unittest.TestCase):
    def draft(self):
        beats = ["opening", "explanations", "evidence", "limits", "next_test"]
        return {
            "status": "review_required", "format": "short",
            "case": {"question": "Fixture topic?"},
            "script": {
                "title": "Fixture", "open_question": "What next?",
                "segments": [{
                    "beat": b,
                    "text": "Fixture spoken text for " + b,
                    "source_urls": ["https://example.org/" + b],
                    "production_note": "Abstract visual for " + b
                } for b in beats]
            }
        }

    def test_build_board_is_explicitly_unreviewed(self):
        board = uvp.build_board(self.draft())
        self.assertEqual(board["reviewer"], "UNREVIEWED_PREVIEW_ONLY")
        self.assertFalse(board["publishable"])
        self.assertEqual(len(board["cues"]), 5)

    def test_visual_prompts_make_six_generated_shots(self):
        prompts = uvp.visual_prompts(uvp.build_board(self.draft()))
        self.assertEqual(len(prompts), 6)
        self.assertEqual(sum(cue == "evidence" for cue, _ in prompts), 2)

    def test_dry_run_uses_existing_episode_adapters(self):
        with tempfile.TemporaryDirectory() as d:
            draft = Path(d) / "draft.json"
            draft.write_text(json.dumps(self.draft()))
            with patch("unreviewed_video_preview.episode.submit_audio",
                       return_value={"opening": {"state": "dry_run"}}) as audio, \
                 patch("unreviewed_video_preview.episode.submit_visual",
                       return_value={"state": "dry_run", "specification": {}}) as visual:
                result = uvp.run(draft, Path(d) / "episode", "voice", "avatar")
            self.assertEqual(result["status"], "dry_run")
            self.assertEqual(visual.call_count, 6)
            audio.assert_called_once()

if __name__ == "__main__":
    unittest.main()
