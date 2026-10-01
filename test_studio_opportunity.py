"""Checks for the hiring format's evidence and distribution boundary."""
import unittest
from unittest.mock import patch

import studio_opportunity as opportunity
import studio_media


class OpportunityBriefTest(unittest.TestCase):
    def setUp(self):
        self.request = {"format": {"id": "opportunity_brief"},
                        "opportunity": {"company": "Example Bio", "role": "Director BD",
                                        "decision_question": "Which clinical partnership should be prioritized?",
                                        "job_url": "https://example.org/jobs/1"}}

    def test_source_brief_keeps_script_citations(self):
        script = {"title": "A partnership decision", "thesis": "One test first",
                  "script": [{"text": "Signal one.", "claim_ids": ["c1"], "citations": ["https://example.org/a"]},
                             {"text": "Our next test.", "claim_ids": [], "citations": []}]}
        note = opportunity.source_brief(script, self.request)
        self.assertEqual(note["cited_points"][0]["sources"], ["https://example.org/a"])
        self.assertEqual(note["status"], "draft_requires_candidate_review")

    def test_invalid_target_does_not_get_normalized(self):
        self.request["opportunity"]["job_url"] = "javascript:alert(1)"
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            opportunity.context(self.request)

    def test_publishing_refuses_outreach_format_before_any_side_effect(self):
        with patch.object(studio_media, "paths", side_effect=AssertionError("must not access media")):
            with self.assertRaisesRegex(ValueError, "publishing is disabled"):
                studio_media.run_publish(".", "test-episode", self.request, "")


if __name__ == "__main__":
    unittest.main()
