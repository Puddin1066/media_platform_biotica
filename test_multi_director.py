import unittest

import asset_coverage
import multi_director
import visual_director


SCRIPT = {
    "positioning": {"positioned_premise": "A men's-health claim sounds stronger than its comparator."},
    "segments": [
        {"beat": "opening", "text": "opening", "production_note": "test",
         "source_urls": [], "monologue_moves": [
            {"function": "cold_open", "text": "The miracle arrives wearing a spreadsheet."},
            {"function": "comic_turn", "text": "Naturally, the spreadsheet has excellent hair."},
        ]},
        {"beat": "explanations", "text": "explanations", "production_note": "test",
         "source_urls": [], "monologue_moves": [
            {"function": "stakes", "text": "Men care because the decision affects treatment."},
            {"function": "escalation", "text": "The claim grows faster than the evidence."},
        ]},
        {"beat": "evidence", "text": "evidence", "production_note": "trial result",
         "source_urls": ["https://example.org/paper"], "monologue_moves": [
            {"function": "receipt", "text": "The trial reports an effect."},
            {"function": "reveal", "text": "The comparator nearly matches it."},
        ]},
        {"beat": "limits", "text": "limits", "production_note": "limitations",
         "source_urls": ["https://example.org/paper"], "monologue_moves": [
            {"function": "reversal", "text": "That changes the interpretation."},
            {"function": "qualification", "text": "The study still leaves uncertainty."},
        ]},
        {"beat": "next_test", "text": "next", "production_note": "next test",
         "source_urls": [], "monologue_moves": [
            {"function": "callback", "text": "Bring back the miracle spreadsheet."},
            {"function": "button", "text": "This time make it show its work."},
        ]},
    ],
}


class CoverageTests(unittest.TestCase):
    def test_library_overproduces_candidates(self):
        direction = visual_director.plan(SCRIPT)
        library = asset_coverage.compile_library(direction, max_motion=4, stills_per_slot=2)
        asset_coverage.validate_library(library)
        self.assertGreaterEqual(library["candidate_count"], 20)
        self.assertLessEqual(library["estimated_runway_credits_if_all_generated"], 120)
        self.assertTrue(any(row["candidate_type"] == "evidence" for row in library["candidates"]))
        self.assertTrue(any(row["candidate_type"] == "generated_motion" for row in library["candidates"]))

    def test_director_tournament_returns_one_choice_per_cue(self):
        direction = visual_director.plan(SCRIPT)
        library = asset_coverage.compile_library(direction)
        result = multi_director.tournament(library)
        self.assertEqual(len(result["edits"]), 3)
        self.assertEqual(len(result["critic"]["selected_edit"]), 6)
        self.assertEqual(result["critic"]["status"], "selected_edit_ready")

    def test_credibility_prefers_evidence_when_available(self):
        direction = visual_director.plan(SCRIPT)
        library = asset_coverage.compile_library(direction)
        edit = multi_director.direct(library, "credibility")
        evidence_choice = next(row for row in edit["selected"] if row["cue_id"] == "evidence")
        self.assertEqual(evidence_choice["candidate_type"], "evidence")


if __name__ == "__main__":
    unittest.main()
