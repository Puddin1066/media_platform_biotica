import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "studio"))
import source_direction


class SourceDirectionTests(unittest.TestCase):
    def setUp(self):
        self.research = {
            "strongest_evidence": [
                {"source_id": "S1", "url": "https://example.org/paper", "author": "Chen", "year": 2025,
                 "finding_supported": "An association", "source_type": "study"},
                {"source_id": "S2", "url": "https://example.org/patent", "author": "Lee", "year": 2024,
                 "finding_supported": "A proposed device", "source_type": "patent"},
            ],
            "claims": [
                {"claim_id": "C1", "status": "supported", "citations": ["S1"]},
                {"claim_id": "C2", "status": "supported_attributed", "citations": ["S2"]},
            ],
        }

    def test_sources_are_spoken_and_linked_to_their_claims(self):
        script = {"script": [
            {"text": "Chen's cohort found an association, and that changes the question.",
             "claim_ids": ["C1"], "spoken_source_id": "S1", "spoken_attribution": "Chen's cohort"},
            {"text": "Lee's patent proposes a device, although it has not shown patient benefit.",
             "claim_ids": ["C2"], "spoken_source_id": "S2", "spoken_attribution": "Lee's patent"},
        ]}
        self.assertEqual(source_direction.script_issues(script, self.research, 60), [])

    def test_metadata_cannot_mask_missing_spoken_source_or_wrong_claim(self):
        script = {"script": [
            {"text": "The data are intriguing.", "claim_ids": ["C2"],
             "spoken_source_id": "S1", "spoken_attribution": "Chen"},
        ]}
        issues = source_direction.script_issues(script, self.research, 60)
        self.assertTrue(any("actually be spoken" in x for x in issues))
        self.assertTrue(any("does not support" in x for x in issues))

    def test_a_scoreboard_is_a_visual_not_a_spoken_sentence(self):
        script = {"script": [{"text": "188, 333, 66, 12, and 9: numbers, numbers, numbers."}]}
        self.assertTrue(any("scoreboard" in x for x in source_direction.script_issues(script, self.research, 60)))


if __name__ == "__main__":
    unittest.main()
