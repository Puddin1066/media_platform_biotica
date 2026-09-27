import json
import unittest
from pathlib import Path

import story_architecture_benchmark as benchmark


class StoryArchitectureBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path("cases/mens-health.json").read_text())
        self.plan = [{"hypothesis_id": "H1", "query": "fixture web question"}]
        self.receipts = [
            {"source_id": "S1", "claim": "Primary result", "title": "Primary paper", "url": "https://example.org/paper"},
            {"source_id": "S2", "claim": "Important limitation", "title": "Review", "url": "https://example.org/review"},
        ]

    def test_pair_uses_identical_receipts_and_only_changes_story_architecture(self):
        pair = benchmark.build_pair(self.case, self.plan, "short", "model", 4, receipts=self.receipts)
        baseline = json.loads(pair["baseline"]["input"])
        story = json.loads(pair["six_stage"]["input"])
        self.assertEqual(baseline["evidence_bundle"], story["evidence_bundle"])
        self.assertNotIn("story_architecture", baseline)
        self.assertIn("story_architecture", story)
        self.assertNotIn("tools", pair["baseline"])
        self.assertNotIn("tools", pair["six_stage"])

    def test_writer_schema_uses_source_ids_not_urls(self):
        segment = benchmark.WRITER_SCHEMA["properties"]["segments"]["items"]["properties"]
        self.assertIn("source_ids", segment)
        self.assertNotIn("source_urls", segment)
        positioning = benchmark.WRITER_SCHEMA["properties"]["positioning"]["properties"]
        self.assertIn("evidence_receipt_source_id", positioning)
        self.assertNotIn("evidence_receipt_url", positioning)

    def test_research_request_is_only_stage_with_web_search(self):
        body = benchmark.research_body(self.case, self.plan, "model", 4)
        self.assertEqual(body["tools"], [{"type": "web_search"}])
        self.assertEqual(body["max_tool_calls"], 4)

    def test_research_discards_fabricated_url_and_keeps_returned_sources(self):
        result = {
            "status": "completed",
            "output": [
                {"type": "web_search_call", "action": {"sources": [
                    {"url": "https://example.org/paper", "title": "Primary paper"},
                    {"url": "https://example.org/review", "title": "Review"},
                ]}},
                {"type": "message", "content": [{"type": "output_text", "text": json.dumps({"receipts": [
                    {"claim": "Primary result", "source_url": "https://example.org/paper", "source_title": "Primary paper"},
                    {"claim": "Important limitation", "source_url": "https://example.org/review", "source_title": "Review"},
                    {"claim": "Invented receipt", "source_url": "https://example.org/not-returned", "source_title": "Fake"},
                ]})}]},
            ],
        }
        receipts = benchmark._parse_research(result)
        self.assertEqual([r["source_id"] for r in receipts], ["S1", "S2"])
        self.assertEqual([r["url"] for r in receipts], ["https://example.org/paper", "https://example.org/review"])

    def test_materialize_rejects_unknown_source_id_before_url_generation(self):
        script = {
            "title": "x", "open_question": "q", "callback_anchor": "anchor",
            "segments": [{"beat": "opening", "text": "x", "source_ids": ["S99"], "production_note": "x", "monologue_moves": []}],
            "positioning": {"evidence_receipt_source_id": "S1"},
        }
        with self.assertRaisesRegex(ValueError, "unknown or missing source_id"):
            benchmark._materialize_source_urls(script, self.receipts)


if __name__ == "__main__":
    unittest.main()
