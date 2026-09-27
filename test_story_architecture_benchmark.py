import json
import unittest
from pathlib import Path

import story_architecture_benchmark as benchmark


class StoryArchitectureBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path("cases/mens-health.json").read_text())
        self.plan = [
            {"hypothesis_id": "H1", "query": "fixture web question"},
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

    def test_structured_json_can_use_returned_web_search_sources_without_annotations(self):
        result = {
            "status": "completed",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {
                        "sources": [
                            {"url": "https://example.org/paper", "title": "Primary paper"}
                        ]
                    },
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({"title": "fixture"}),
                            "annotations": [],
                        }
                    ],
                },
            ],
        }
        script, sources = benchmark._parse_benchmark_response(result)
        self.assertEqual(script, {"title": "fixture"})
        self.assertEqual(sources[0]["url"], "https://example.org/paper")
        self.assertEqual(sources[0]["role"], "consulted")

    def test_reconcile_maps_benign_url_variants_to_exact_returned_source(self):
        exact = "https://example.org/paper?a=1&b=2"
        script = {
            "segments": [
                {"source_urls": ["https://EXAMPLE.org/paper/?utm_source=x&b=2&a=1#results"]}
            ],
            "positioning": {"evidence_receipt_url": "https://example.org/paper/?b=2&a=1"},
        }
        reconciled = benchmark._reconcile_script_urls(script, [exact])
        self.assertEqual(reconciled["segments"][0]["source_urls"], [exact])
        self.assertEqual(reconciled["positioning"]["evidence_receipt_url"], exact)

    def test_reconcile_rejects_genuinely_unreturned_source(self):
        script = {
            "segments": [{"source_urls": ["https://other.example/paper"]}],
            "positioning": {"evidence_receipt_url": "https://example.org/paper"},
        }
        with self.assertRaisesRegex(ValueError, "other.example"):
            benchmark._reconcile_script_urls(script, ["https://example.org/paper"])


if __name__ == "__main__":
    unittest.main()
