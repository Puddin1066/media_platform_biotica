import os
import unittest

import story_architecture


class StoryArchitectureTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "question": "Does TRT cardiovascular risk still match the conventional warning?",
            "canon": "Men's health evidence investigation",
            "hypotheses": [
                {"id": "h1", "statement": "The warning overstates current cardiovascular evidence."},
                {"id": "h2", "statement": "Secondary safety signals still justify caution."},
            ],
        }

    def test_build_has_six_causal_stages(self):
        contract = story_architecture.build(self.case, "short")
        self.assertEqual(contract["sequence"], list(story_architecture.STAGES))
        self.assertEqual(len(contract["stages"]), 6)
        self.assertEqual(contract["stages"][0]["name"], "prevailing_belief")
        self.assertEqual(contract["stages"][-1]["name"], "satoshi_synthesis")

    def test_competing_explanations_are_explicit(self):
        contract = story_architecture.build(self.case)
        stage = next(x for x in contract["stages"] if x["name"] == "competing_explanations")
        self.assertIn("at least two", stage["job"])

    def test_short_contract_preserves_compression(self):
        contract = story_architecture.build(self.case, "short")
        self.assertTrue(any("compress adjacent stages" in rule for rule in contract["rules"]))

    def test_beat_mapping_preserves_existing_pipeline(self):
        mapping = story_architecture.beat_mapping()
        self.assertEqual(set(mapping), {"opening", "explanations", "evidence", "limits", "next_test"})
        self.assertIn("satoshi_synthesis", mapping["next_test"])
        self.assertIn("destabilizing_receipt", mapping["evidence"])

    def test_enabled_can_be_disabled_for_ab_test(self):
        old = os.environ.get("SATOSHI_STORY_ARCHITECTURE_ENABLED")
        try:
            os.environ["SATOSHI_STORY_ARCHITECTURE_ENABLED"] = "false"
            self.assertFalse(story_architecture.enabled())
            os.environ["SATOSHI_STORY_ARCHITECTURE_ENABLED"] = "true"
            self.assertTrue(story_architecture.enabled())
        finally:
            if old is None:
                os.environ.pop("SATOSHI_STORY_ARCHITECTURE_ENABLED", None)
            else:
                os.environ["SATOSHI_STORY_ARCHITECTURE_ENABLED"] = old

    def test_missing_case_question_is_rejected(self):
        with self.assertRaises(ValueError):
            story_architecture.build({"hypotheses": [{"id": "h1", "statement": "x"}]})


if __name__ == "__main__":
    unittest.main()
