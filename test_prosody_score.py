import unittest

import prosody_score


class ProsodyScoreTests(unittest.TestCase):
    def test_opening_moves_from_hook_to_intrigue(self):
        score = prosody_score.performance_score(
            "opening",
            "Tetris may have accidentally become medicine. And the weaker claim is stranger than the strong one.",
        )
        self.assertEqual([item["role"] for item in score], ["hook", "intrigue"])

    def test_correction_is_skeptical_not_hype(self):
        score = prosody_score.performance_score(
            "evidence",
            "That does not mean Tetris treats PTSD.",
        )
        self.assertEqual(score[0]["role"], "correction")
        self.assertIn("negation", score[0]["direction"])

    def test_joke_is_underplayed(self):
        score = prosody_score.performance_score(
            "explanations",
            "World of Warcraft is basically middle management with dragons.",
        )
        self.assertEqual(score[0]["role"], "dry_humor")
        self.assertIn("underplay", score[0]["direction"])

    def test_evidence_gets_receipt_delivery(self):
        score = prosody_score.performance_score(
            "evidence",
            "Researchers reported fewer intrusive memories in the study.",
        )
        self.assertEqual(score[0]["role"], "receipt")
        self.assertIn("factual", score[0]["direction"])

    def test_final_sentence_is_payoff(self):
        score = prosody_score.performance_score(
            "next_test",
            "Maybe digital therapeutics should search backward. Your chemical library is Steam.",
        )
        self.assertEqual(score[0]["role"], "synthesis")
        self.assertEqual(score[1]["role"], "dry_humor")

    def test_instructions_direct_sentence_level_variation(self):
        instructions, score = prosody_score.performance_instructions(
            "Base persona.",
            "limits",
            "Selection effects matter. That does not make the mechanism useless.",
        )
        self.assertEqual(len(score), 2)
        self.assertIn("Sentence 1", instructions)
        self.assertIn("Sentence 2", instructions)
        self.assertIn("Change prosody between sentences", instructions)
        self.assertIn("constant pitch", instructions)


if __name__ == "__main__":
    unittest.main()
