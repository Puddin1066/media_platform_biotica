import json
import unittest

import editorial_short


class EditorialShortTests(unittest.TestCase):
    def setUp(self):
        self.case = {"question": "Does TRT change cardiovascular risk?", "canon": "TRT safety"}
        self.receipts = [
            {"source_id": "S1", "claim": "Primary outcome was noninferior", "title": "Trial", "url": "https://example.org/trial"},
            {"source_id": "S2", "claim": "Some secondary signals differed", "title": "Review", "url": "https://example.org/review"},
        ]

    def test_only_constrained_opening_strategies_are_allowed(self):
        for strategy in editorial_short.OPENING_STRATEGIES:
            body = editorial_short.request_body(self.case, "model", self.receipts, strategy)
            brief = json.loads(body["input"])
            self.assertEqual(brief["opening_strategy"], strategy)
            self.assertIn("one coherent narrative", brief["assignment"])
            self.assertIn("not four prose blocks", brief["assignment"])
        with self.assertRaisesRegex(ValueError, "Unknown opening strategy"):
            editorial_short.request_body(self.case, "model", self.receipts, "random_shuffle")

    def test_writer_has_no_web_search_or_urls(self):
        body = editorial_short.request_body(self.case, "model", self.receipts, "receipt_first")
        self.assertNotIn("tools", body)
        brief = json.loads(body["input"])
        self.assertNotIn("url", json.dumps(brief["evidence_bundle"]).lower())

    def test_materialize_keeps_one_continuous_script_and_maps_sources(self):
        script = {
            "title": "TRT got stranger",
            "opening_strategy": "wrinkle_first",
            "script_text": "The testosterone heart-risk story got stranger. A large trial eased the main cardiovascular concern, but some secondary signals still complicate the clean victory lap. That changes the old blanket-risk story without proving testosterone is harmless. The interesting question now is which men, if any, actually account for the remaining signal.",
            "open_question": "Who accounts for the remaining signal?",
            "beats": [
                {"beat": "interesting_thing", "summary": "Old risk story changed", "source_ids": ["S1"], "production_note": "label history"},
                {"beat": "receipt", "summary": "Large trial result", "source_ids": ["S1"], "production_note": "trial card"},
                {"beat": "meaning", "summary": "Blanket risk claim weakened", "source_ids": ["S1"], "production_note": "host"},
                {"beat": "remaining_weirdness", "summary": "Secondary signals remain", "source_ids": ["S2"], "production_note": "secondary endpoint card"},
            ],
        }
        result = editorial_short.materialize(script, self.receipts)
        self.assertEqual(result["opening_strategy"], "wrinkle_first")
        self.assertIn("The testosterone heart-risk story", result["script_text"])
        self.assertEqual(result["editorial_annotations"][1]["source_urls"], ["https://example.org/trial"])
        self.assertNotIn("beats", result)

    def test_unknown_source_id_fails_closed(self):
        script = {
            "title": "x",
            "opening_strategy": "observation_first",
            "script_text": "A short coherent script.",
            "open_question": "What next?",
            "beats": [
                {"beat": beat, "summary": "x", "source_ids": ["S9"], "production_note": "x"}
                for beat in editorial_short.BEATS
            ],
        }
        with self.assertRaisesRegex(ValueError, "Unknown or missing source_id"):
            editorial_short.materialize(script, self.receipts)


if __name__ == "__main__":
    unittest.main()
