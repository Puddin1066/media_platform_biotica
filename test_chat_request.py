import unittest

import chat_request


class ChatRequestTests(unittest.TestCase):
    def test_resolves_conversation_into_creative_angle(self):
        request = {
            "topic": "testosterone and cardiovascular risk",
            "opening_strategy": "wrinkle_first",
            "editorial_notes": "The interesting story is that the old warning weakened without making the story simple.",
            "candidate_lines": ["The warning got quieter. The biology didn't."],
            "must_keep_lines": ["somehow the story got stranger"],
            "timing_notes": "Pause after the trial result.",
            "avoid": ["salesy hook", "subscribe CTA"],
        }
        out = chat_request.resolve(request)
        self.assertEqual(out["opening_strategy"], "wrinkle_first")
        self.assertIn("somehow the story got stranger", out["angle"])
        self.assertIn("Pause after the trial result", out["angle"])
        self.assertIn("Creative direction only", out["angle"])

    def test_editorial_lines_are_not_promoted_to_evidence(self):
        out = chat_request.resolve({
            "topic": "male fertility",
            "candidate_lines": ["Sperm counts fell 80 percent"],
        })
        self.assertIn("factual claims still require web-researched evidence", out["angle"])
        self.assertNotIn("sources", out)

    def test_rejects_unknown_opening(self):
        with self.assertRaises(ValueError):
            chat_request.resolve({"topic": "male fertility", "opening_strategy": "random_shuffle"})

    def test_rejects_unbounded_budget(self):
        with self.assertRaises(ValueError):
            chat_request.resolve({"topic": "male fertility", "max_openai_usd": 50})


if __name__ == "__main__":
    unittest.main()
