import unittest
import positioning

URL = "https://example.org/paper"

def fixture():
    return {
        "territory": "fertility_reproductive",
        "male_consequence": "fertility",
        "prevailing_belief": "Heat is either harmless or obviously catastrophic for sperm.",
        "evidence_conflict": "Human studies suggest measurable changes, but reversibility and magnitude vary.",
        "evidence_receipt": "A human study reports semen changes after repeated heat exposure.",
        "evidence_receipt_url": URL,
        "audience_tension": "Men want heat exposure benefits without quietly trading off fertility.",
        "share_trigger": "A sauna-using man could send this to a friend who tracks fertility or testosterone.",
        "positioned_premise": "Heat exposure may affect sperm, but the male-health question is how much and whether it reverses.",
        "hook_variants": [
            {"type": "threat_tradeoff", "text": "Your sauna habit may be costing your sperm more than you think."},
            {"type": "conflict", "text": "Sauna is sold as healthy, but your sperm may have a different opinion."},
            {"type": "counterintuitive_receipt", "text": "Human semen data make the sauna story much less simple."},
        ],
    }

class PositioningTests(unittest.TestCase):
    def test_accepts_specific_mens_health_positioning(self):
        result = positioning.validate(fixture(), [URL])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["territory"], "fertility_reproductive")

    def test_rejects_generic_or_uncited_receipt(self):
        value = fixture()
        value["evidence_receipt_url"] = "https://example.org/uncited"
        with self.assertRaises(ValueError):
            positioning.validate(value, [URL])

    def test_requires_three_distinct_hooks(self):
        value = fixture()
        value["hook_variants"] = value["hook_variants"][:2]
        with self.assertRaises(ValueError):
            positioning.validate(value, [URL])

if __name__ == "__main__":
    unittest.main()
