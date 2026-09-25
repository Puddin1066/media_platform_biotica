import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import unreviewed_video_preview as uvp
import visual_director

class PreviewVideoTests(unittest.TestCase):
    def draft(self):
        rows = {
            "opening": [
                ("cold_open", "The hot seat may be biologically literal."),
                ("comic_turn", "Your testicles did not sign that lease.")],
            "explanations": [
                ("stakes", "Heat exposure can raise scrotal temperature enough to matter."),
                ("escalation", "That is an awkward thermostat problem.")],
            "evidence": [
                ("receipt", "Human studies report semen changes after repeated heat exposure."),
                ("reveal", "So the signal is not purely theoretical.")],
            "limits": [
                ("reversal", "But observational data cannot isolate every behavior or timing effect."),
                ("qualification", "The evidence has more asterisks than confidence.")],
            "next_test": [
                ("callback", "The hot seat question is whether recovery follows cooling."),
                ("button", "That is the experiment worth watching.")],
        }
        segments = []
        for beat, moves in rows.items():
            mm = [{"function": fn, "text": text} for fn, text in moves]
            segments.append({
                "beat": beat,
                "text": " ".join(m["text"] for m in mm),
                "source_urls": ["https://example.org/" + beat],
                "production_note": "Abstract visual for " + beat,
                "monologue_moves": mm,
            })
        return {
            "status": "review_required", "format": "short",
            "case": {"question": "Fixture topic?"},
            "script": {
                "title": "Fixture",
                "open_question": "What next?",
                "callback_anchor": "hot seat",
                "positioning": {
                    "territory": "fertility_reproductive",
                    "male_consequence": "fertility",
                    "prevailing_belief": "Heat is either harmless or obviously catastrophic for sperm.",
                    "evidence_conflict": "Human studies suggest changes, but magnitude and reversibility vary.",
                    "evidence_receipt": "A human study reports semen changes after repeated heat exposure.",
                    "evidence_receipt_url": "https://example.org/evidence",
                    "audience_tension": "Men want heat benefits without quietly trading off fertility.",
                    "share_trigger": "A sauna-using man could send this to a friend tracking fertility.",
                    "positioned_premise": "Heat may affect sperm, but the key question is how much and whether it reverses.",
                    "hook_variants": [
                        {"type": "threat_tradeoff", "text": "Your sauna habit may be costing your sperm more than you think."},
                        {"type": "conflict", "text": "Sauna is sold as healthy, but your sperm may have a different opinion."},
                        {"type": "counterintuitive_receipt", "text": "Human semen data make the sauna story much less simple."}
                    ],
                },
                "segments": segments,
            }
        }

    def test_build_board_is_explicitly_unreviewed(self):
        board = uvp.build_board(self.draft())
        self.assertEqual(board["reviewer"], "UNREVIEWED_PREVIEW_ONLY")
        self.assertFalse(board["publishable"])
        self.assertEqual(len(board["cues"]), 5)

    def test_visual_direction_has_ten_events_and_six_render_slots(self):
        direction = visual_director.plan(self.draft()["script"])
        self.assertEqual(len(direction["events"]), 10)
        self.assertEqual(len(direction["render_slots"]), 6)
        self.assertEqual(direction["render_slots"][0]["visual_function"], "pattern_interrupt")
        self.assertEqual(direction["render_slots"][3]["visual_function"], "evidence_receipt")
        self.assertEqual(direction["render_slots"][5]["visual_function"], "callback_visual")

    def test_visual_prompts_compile_to_six_generated_shots(self):
        direction = visual_director.plan(self.draft()["script"])
        prompts = uvp.visual_prompts(direction)
        self.assertEqual(len(prompts), 6)
        self.assertEqual(sum(cue == "opening" for cue, _ in prompts), 2)
        self.assertEqual(sum(cue == "evidence" for cue, _ in prompts), 1)

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
            self.assertTrue((Path(d) / "episode" / "visual-direction.json").exists())
            audio.assert_called_once()

if __name__ == "__main__":
    unittest.main()
