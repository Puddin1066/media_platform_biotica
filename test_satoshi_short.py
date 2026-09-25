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
        return {
                "title": "Fixture web draft",
                "open_question": "What still needs a discriminating test?",
                "callback_anchor": "hot seat",
                "segments": [
                        {
                                "beat": "opening",
                                "text": "The hot seat may be biologically literal. Your testicles did not sign that lease.",
                                "source_urls": [
                                        "https://example.org/paper"
                                ],
                                "production_note": "Proposed visual only",
                                "monologue_moves": [
                                        {
                                                "function": "cold_open",
                                                "text": "The hot seat may be biologically literal."
                                        },
                                        {
                                                "function": "comic_turn",
                                                "text": "Your testicles did not sign that lease."
                                        }
                                ]
                        },
                        {
                                "beat": "explanations",
                                "text": "Heat exposure can raise scrotal temperature enough to matter. That is an awkward thermostat problem.",
                                "source_urls": [
                                        "https://example.org/paper"
                                ],
                                "production_note": "Proposed visual only",
                                "monologue_moves": [
                                        {
                                                "function": "stakes",
                                                "text": "Heat exposure can raise scrotal temperature enough to matter."
                                        },
                                        {
                                                "function": "escalation",
                                                "text": "That is an awkward thermostat problem."
                                        }
                                ]
                        },
                        {
                                "beat": "evidence",
                                "text": "Human studies report semen changes after repeated heat exposure. So the signal is not purely theoretical.",
                                "source_urls": [
                                        "https://example.org/paper"
                                ],
                                "production_note": "Proposed visual only",
                                "monologue_moves": [
                                        {
                                                "function": "receipt",
                                                "text": "Human studies report semen changes after repeated heat exposure."
                                        },
                                        {
                                                "function": "reveal",
                                                "text": "So the signal is not purely theoretical."
                                        }
                                ]
                        },
                        {
                                "beat": "limits",
                                "text": "But observational data cannot isolate every behavior or timing effect. The evidence has more asterisks than confidence.",
                                "source_urls": [
                                        "https://example.org/paper"
                                ],
                                "production_note": "Proposed visual only",
                                "monologue_moves": [
                                        {
                                                "function": "reversal",
                                                "text": "But observational data cannot isolate every behavior or timing effect."
                                        },
                                        {
                                                "function": "qualification",
                                                "text": "The evidence has more asterisks than confidence."
                                        }
                                ]
                        },
                        {
                                "beat": "next_test",
                                "text": "The hot seat question is whether recovery follows cooling. That is the experiment worth watching.",
                                "source_urls": [
                                        "https://example.org/paper"
                                ],
                                "production_note": "Proposed visual only",
                                "monologue_moves": [
                                        {
                                                "function": "callback",
                                                "text": "The hot seat question is whether recovery follows cooling."
                                        },
                                        {
                                                "function": "button",
                                                "text": "That is the experiment worth watching."
                                        }
                                ]
                        }
                ]
        }

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
