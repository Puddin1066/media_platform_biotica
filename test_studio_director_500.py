"""The director packet is a review gate, not a media submission."""
import unittest

import studio_director_500 as director_500


class Director500Tests(unittest.TestCase):
    script = {"title": "An unexpected result", "target_seconds": 60,
              "script": [{"sentence_id": "s01", "text": "The result surprised us."}]}
    visual = {"shots": [{"shot_id": "sh01", "sentence_ids": ["s01"],
                         "type": "generated illustration"}]}

    def directions(self):
        return {"hero": {"model": "seedance2_5", "resolution": "720p", "seconds": 8,
                         "prompt": "The presenter enters a spare laboratory and sees a stack of papers tipping over. The camera tracks his reaction."},
                "moving_shots": [{"shot_id": "sh01", "model": "gen4_turbo", "seconds": 4,
                                  "prompt": "The paper stack tilts slowly while the camera pushes in."}],
                "new_stills": 12, "audio_credits": 10}

    def test_formula_reserves_a_paid_retry(self):
        packet = director_500.compile_packet(self.script, self.visual, self.directions())
        self.assertEqual(packet["budget"]["ceiling_credits"], 500)
        self.assertEqual(packet["budget"]["first_pass_credits"], 302)
        self.assertEqual(packet["budget"]["retry_reserve_credits"], 198)
        self.assertEqual(packet["review"]["status"], "pending")
        self.assertEqual(packet["moving_shots"][0]["source_sentence_ids"], ["s01"])

    def test_cap_scales_with_finished_duration(self):
        plan = director_500.compile_packet(self.script, self.visual, self.directions(),
                                           {"target_seconds": 90})
        self.assertEqual(plan["budget"]["ceiling_credits"], 750)
        with self.assertRaisesRegex(ValueError, "reserve"):
            director_500.compile_packet(self.script, self.visual, self.directions(),
                                        {"target_seconds": 45})

    def test_rejects_fabricated_source_motion_and_excess_spend(self):
        d = self.directions()
        d["moving_shots"][0]["shot_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "existing shot"):
            director_500.compile_packet(self.script, self.visual, d)
        d = self.directions()
        d["hero"]["native_dialogue"] = "A purported quote"
        with self.assertRaisesRegex(ValueError, "dialogue"):
            director_500.compile_packet(self.script, self.visual, d)
        d = self.directions()
        d["hero"]["seconds"] = 10
        d["moving_shots"][0]["seconds"] = 10
        with self.assertRaisesRegex(ValueError, "reserve"):
            director_500.compile_packet(self.script, self.visual, d)


if __name__ == "__main__":
    unittest.main()
