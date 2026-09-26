import unittest

import content_strategy


class ContentStrategyTests(unittest.TestCase):
    def test_config_is_complete_and_balanced(self):
        config = content_strategy.load_config()
        self.assertEqual(len(config["pillars"]), 6)
        self.assertAlmostEqual(sum(p["target_share"] for p in config["pillars"]), 1.0)
        self.assertEqual(config["pillars"][0]["id"], "hormones")

    def test_user_topic_is_preserved_verbatim(self):
        topic = "Are sperm counts actually collapsing?"
        pillar = content_strategy.get_pillar("fertility")
        value = content_strategy.brief(pillar, topic)
        self.assertEqual(value["topic"], topic)
        self.assertEqual(value["topic_authority"], "user_or_explicit_upstream_input")

    def test_unknown_pillar_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown content pillar"):
            content_strategy.get_pillar("invented")

    def test_conspiracy_files_require_counter_case_and_verdict(self):
        pillar = content_strategy.get_pillar("conspiracy_files")
        brief = content_strategy.brief(pillar, "Who benefits from normal testosterone ranges?")
        self.assertIn("strongest counter-case", brief["required_structure"])
        self.assertIn("MOSTLY INTERNET MYTH", brief["allowed_verdicts"])
        self.assertIn("INSUFFICIENT EVIDENCE", brief["allowed_verdicts"])


if __name__ == "__main__":
    unittest.main()
