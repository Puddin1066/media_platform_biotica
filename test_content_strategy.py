import unittest

import content_strategy


class ContentStrategyTests(unittest.TestCase):
    def test_config_is_complete_and_balanced(self):
        config = content_strategy.load_config()
        self.assertEqual(len(config["pillars"]), 6)
        self.assertAlmostEqual(sum(p["target_share"] for p in config["pillars"]), 1.0)
        self.assertEqual(config["pillars"][0]["id"], "hormones")

    def test_empty_history_starts_with_largest_target(self):
        pillar = content_strategy.next_pillar([])
        self.assertEqual(pillar["id"], "hormones")

    def test_planner_corrects_overrepresented_pillar(self):
        history = [{"pillar": "hormones"} for _ in range(10)]
        pillar = content_strategy.next_pillar(history)
        self.assertNotEqual(pillar["id"], "hormones")

    def test_conspiracy_files_require_counter_case_and_verdict(self):
        config = content_strategy.load_config()
        pillar = next(p for p in config["pillars"] if p["id"] == "conspiracy_files")
        brief = content_strategy.brief(pillar)
        self.assertIn("strongest counter-case", brief["required_structure"])
        self.assertIn("MOSTLY INTERNET MYTH", brief["allowed_verdicts"])
        self.assertIn("INSUFFICIENT EVIDENCE", brief["allowed_verdicts"])


if __name__ == "__main__":
    unittest.main()
