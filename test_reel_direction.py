"""The reel shape, the read, and the cut are production gates, not taste notes."""
import json
import unittest
from pathlib import Path

import reel_direction
import satoshi_editorial_pipeline as editorial


EPISODE = Path("studio/episodes/northeastern-video-2026-10-01/artifacts")
LECTURE = Path("fixtures/rejected-spinout-lecture")


def spoken(*lines):
    return {"script": [{"sentence_id": f"s{i:02d}", "text": text, "function": function}
                        for i, (text, function) in enumerate(lines, 1)]}


class ReelDirectionTests(unittest.TestCase):
    def test_the_spinout_lecture_never_reaches_voice_or_picture(self):
        script = json.loads((LECTURE / "canonical_script.json").read_text())
        with self.assertRaisesRegex(ValueError, "scoreboard|disclaimer|inversion|lecture"):
            reel_direction.assert_reel_shape(script)

    def test_the_locked_spinout_reel_passes_the_shape_gate(self):
        script = json.loads((EPISODE / "canonical_script.json").read_text())
        reel_direction.assert_reel_shape(script)
        spoken_text = " ".join(sentence["text"] for sentence in script["script"])
        self.assertIn("still in the mail", spoken_text)
        self.assertIn("developing", spoken_text)
        self.assertIn("claims", spoken_text)
        self.assertIn("still listed active", spoken_text)
        self.assertIn("Launching is not the same verb as lasting.", spoken_text)
        self.assertNotIn("failure", spoken_text.lower())
        self.assertNotIn("survived", spoken_text.lower())

    def test_a_four_beat_reel_passes_the_shape_gate(self):
        script = spoken(
            ("A patent is a permission slip.", "hook"),
            ("InLoop claims a next-day orthotic.", "receipt"),
            ("That is a product claim, not a clinic result.", "boundary"),
            ("Surviving is the business.", "payoff"),
        )
        reel_direction.assert_reel_shape(script)

    def test_performance_prompt_uses_pace_and_drops_essay_direction(self):
        prosody = {
            "global_direction": "Keep it dry.",
            "sentences": [
                {"sentence_id": "s01", "pace": "brisk", "pause_before_ms": 0,
                 "emphasis": "permission slip", "direction": "pause " * 80},
                {"sentence_id": "s02", "pace": "deliberate", "pause_before_ms": 320,
                 "emphasis": "This emphasis is a whole paragraph and must not be spoken as an instruction."},
            ],
        }
        prompt = editorial.performance_prompt({"script": []}, prosody, "b")
        self.assertLessEqual(len(prompt), 900)
        self.assertIn("Keep it dry.", prompt)
        self.assertIn("s01 brisk", prompt)
        self.assertIn("hit permission slip", prompt)
        self.assertIn("s02 deliberate", prompt)
        self.assertIn("pause 320ms", prompt)
        self.assertNotIn("pause pause", prompt)
        self.assertNotIn("whole paragraph", prompt)

    def test_cards_hit_the_word_and_do_not_cover_the_sentence(self):
        plan = json.loads((LECTURE / "visual_plan.json").read_text())
        timing = json.loads((LECTURE / "narration_alignment.json").read_text())
        shots = []
        for shot in plan["shots"]:
            kind = shot["type"].replace("_", " ")
            visual = {"typography": "typography", "chart": "chart"}.get(kind, "illustration")
            shots.append({**shot, "visual_type": visual, "citations": []})
        beats = reel_direction.direct_picture(shots, timing)
        self.assertEqual(beats[0]["visual_type"], "host")
        self.assertGreaterEqual(beats[0]["end_ms"] - beats[0]["start_ms"], 1000)
        cards = [beat for beat in beats if beat["visual_type"] != "host"]
        self.assertTrue(cards)
        self.assertTrue(all(beat["end_ms"] - beat["start_ms"] <= 8100 for beat in cards))
        by_id = {beat["beat_id"]: beat for beat in cards}
        sentences = {item["sentence_id"]: item for item in timing["sentences"]}
        receipt = by_id["sh02"]
        self.assertGreater(receipt["start_ms"], sentences["s02"]["startMs"] + 1000)
        self.assertLess(receipt["end_ms"] - receipt["start_ms"], sentences["s02"]["endMs"] - sentences["s02"]["startMs"])
        self.assertEqual(by_id["sh04"]["motion"], "hold")
        self.assertEqual(cards[-1]["motion"], "crossfade")


if __name__ == "__main__":
    unittest.main()
