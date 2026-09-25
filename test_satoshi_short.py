import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import satoshi_short
import short_format
import topic_case

class TopicCaseTests(unittest.TestCase):
    def test_builds_valid_case_from_topic(self):
        case = topic_case.build("microplastics and male fertility")
        self.assertTrue(case["question"].startswith("What does the best current evidence show"))
        self.assertEqual(len(case["hypotheses"]), 4)
        self.assertEqual(case["claims"], [])

class ShortFormatTests(unittest.TestCase):
    def fixture(self):
        beats = ["opening", "explanations", "evidence", "limits", "next_test"]
        texts = [
            "Heat may matter more than your supplements.",
            "The question is whether exposure changes sperm production enough to matter.",
            "Human studies report measurable differences, but the size varies by population.",
            "Most studies are observational, so behavior and timing can distort the signal.",
            "The real test is whether repeated measurements recover after exposure stops."
        ]
        return {"segments": [
            {"beat": b, "text": t, "source_urls": ["https://example.org/a"],
             "production_note": "Show a reviewed source receipt"}
            for b, t in zip(beats, texts)
        ]}
    def test_accepts_compact_source_backed_short(self):
        result = short_format.validate_script(self.fixture())
        self.assertEqual(result["status"], "pass")
        self.assertLessEqual(result["spoken_words"], 95)
    def test_rejects_intro(self):
        script = self.fixture()
        script["segments"][0]["text"] = "Today we are going to discuss male fertility."
        with self.assertRaises(ValueError):
            short_format.validate_script(script)

class OrchestratorTests(unittest.TestCase):
    def test_dry_prepare_makes_no_provider_call(self):
        with tempfile.TemporaryDirectory() as d, patch("satoshi_short.produce.run") as run:
            run.return_value = {"status": "ready_for_configured_live_call",
                                "mode": "dry_run", "publishable": False}
            result = satoshi_short.prepare("sauna and sperm quality", "", d)
            self.assertEqual(result["mode"], "dry_run")
            self.assertTrue((Path(d) / "topic-case.json").exists())

    def test_live_research_packages_validated_script(self):
        script = ShortFormatTests().fixture()
        script.update({"title": "Fixture", "open_question": "What changes next?"})
        draft = {"status": "review_required", "format": "short",
                 "script": script, "sources": [{"url": "https://example.org/a", "role": "cited"}]}
        with tempfile.TemporaryDirectory() as d:
            draft_dir = Path(d) / "draft"
            draft_dir.mkdir()
            (draft_dir / "draft.json").write_text(json.dumps(draft))
            (draft_dir / "script.md").write_text("# fixture")
            with patch("satoshi_short.produce.run", return_value={
                "status": "review_required", "path": str(draft_dir), "publishable": False
            }):
                result = satoshi_short.prepare("sauna and sperm quality", "", Path(d) / "out",
                                               live=True, budget=1, max_usd_per_run=.25)
            self.assertEqual(result["status"], "review_required")
            self.assertTrue((Path(d) / "out" / "validation-report.json").exists())

if __name__ == "__main__":
    unittest.main()
