import json
import unittest

import story_architecture_benchmark as benchmark


class StoryArchitectureBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.case = {
            "question": "Does TRT cardiovascular risk still match the conventional warning?",
            "canon": "Men's health evidence investigation",
            "hypotheses": [
                {"id": "h1", "statement": "Current cardiovascular evidence is more reassuring."},
                {"id": "h2", "statement": "Secondary safety findings preserve important uncertainty."},
            ],
        }
        self.plan = [
            {"hypothesis_id": "h1", "query": "TRT cardiovascular trial evidence"},
            {"hypothesis_id": "h2", "query": "TRT secondary safety signals"},
        ]

    def test_pair_changes_story_context_not_tools_or_schema(self):
        pair = benchmark.build_pair(self.case, self.plan, "short", "model", 4)
        baseline = json.loads(pair["baseline"]["input"])
        story = json.loads(pair["six_stage"]["input"])
        self.assertNotIn("story_architecture", baseline)
        self.assertIn("story_architecture", story)
        self.assertEqual(pair["baseline"]["tools"], pair["six_stage"]["tools"])
        self.assertEqual(pair["baseline"]["text"], pair["six_stage"]["text"])
        self.assertEqual(pair["baseline"]["max_tool_calls"], pair["six_stage"]["max_tool_calls"])

    def test_story_request_keeps_existing_five_beats(self):
        body = benchmark.architecture_body(self.case, self.plan, "short", "model", 4)
        brief = json.loads(body["input"])
        self.assertEqual(brief["required_beats"], ["opening", "explanations", "evidence", "limits", "next_test"])
        self.assertEqual(brief["story_architecture"]["version"], "six-stage-v1")

    def test_story_assignment_requires_competing_explanations(self):
        body = benchmark.architecture_body(self.case, self.plan, "short", "model", 4)
        brief = json.loads(body["input"])
        self.assertIn("at least two plausible competing explanations", brief["assignment"])
        self.assertIn("Background earns space only", brief["assignment"])


if __name__ == "__main__":
    unittest.main()
