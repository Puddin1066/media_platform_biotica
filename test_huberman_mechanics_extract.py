import unittest

import huberman_mechanics_extract as hme


class HubermanMechanicsExtractTests(unittest.TestCase):
    def _valid_result(self):
        return {
            "mechanics": [
                {
                    "function": "hook",
                    "mechanic": f"Open with a bounded question and define the decision the audience must resolve {i}.",
                    "when_to_use": "Use when the topic contains a genuine uncertainty with practical stakes.",
                    "avoid": "Avoid manufacturing uncertainty or implying a factual conclusion before evidence is shown.",
                }
                for i in range(5)
            ]
        }

    def test_request_uses_central_model_role(self):
        payload = hme._request_payload("source", "episode-1")
        self.assertIsInstance(payload["model"], str)
        self.assertTrue(payload["model"])

    def test_neutralized_result_passes_without_creator_reference(self):
        source = "A completely different source passage about biology and experimental design."
        self.assertEqual(hme.validate_neutralized(source, self._valid_result()), self._valid_result())

    def test_rejects_creator_reference(self):
        result = self._valid_result()
        result["mechanics"][0]["mechanic"] = "Use Huberman's method to structure the explanation."
        with self.assertRaises(ValueError):
            hme.validate_neutralized("unrelated source", result)

    def test_rejects_long_verbatim_overlap(self):
        repeated = "alpha beta gamma delta epsilon zeta eta theta"
        source = f"prefix {repeated} suffix"
        result = self._valid_result()
        result["mechanics"][0]["mechanic"] = repeated
        with self.assertRaises(ValueError):
            hme.validate_neutralized(source, result)


if __name__ == "__main__":
    unittest.main()
