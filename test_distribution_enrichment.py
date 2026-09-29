import unittest

import distribution_enrichment as d


class DistributionEnrichmentTests(unittest.TestCase):
    def test_specific_hashtags_are_kept_and_generic_spam_removed(self):
        packet = d.sanitize({
            "entities": [],
            "hashtags": [
                {"tag": "#Theranos", "reason": "subject", "category": "subject", "confidence": 0.99},
                {"tag": "#viral", "reason": "reach", "category": "generic", "confidence": 1.0},
                {"tag": "#Diagnostics", "reason": "category", "category": "audience", "confidence": 0.9},
            ],
            "mentions": [],
            "caption_text": "The diagnostic scandal was not really about one blood test.",
            "share_to_feed": True,
        })
        tags = [x["tag"] for x in packet["hashtags"]]
        self.assertEqual(tags, ["#Theranos", "#Diagnostics"])
        self.assertNotIn("#viral", packet["caption"])

    def test_hashtags_are_deduplicated_and_capped(self):
        hashtags = [
            {"tag": f"#Topic{i}", "reason": "topic", "category": "subject", "confidence": 1 - i * 0.01}
            for i in range(8)
        ]
        hashtags.append({"tag": "#topic0", "reason": "duplicate", "category": "subject", "confidence": 0.5})
        packet = d.sanitize({
            "entities": [], "hashtags": hashtags, "mentions": [],
            "caption_text": "Caption", "share_to_feed": True,
        })
        self.assertEqual(len(packet["hashtags"]), 6)
        self.assertEqual(packet["hashtags"][0]["tag"], "#Topic0")

    def test_verified_matching_instagram_handle_is_allowed(self):
        packet = d.sanitize({
            "entities": [], "hashtags": [],
            "mentions": [{
                "entity": "Nature", "handle": "@nature", "confidence": 0.97,
                "verification_url": "https://www.instagram.com/nature/", "reason": "source journal",
            }],
            "caption_text": "A paper worth reading.", "share_to_feed": True,
        })
        self.assertEqual(packet["mentions"][0]["handle"], "@nature")
        self.assertIn("@nature", packet["caption"])

    def test_guessed_or_mismatched_handle_is_dropped(self):
        packet = d.sanitize({
            "entities": [], "hashtags": [],
            "mentions": [
                {"entity": "Nature", "handle": "@nature", "confidence": 0.99,
                 "verification_url": "https://example.com/nature", "reason": "not Instagram"},
                {"entity": "Nature", "handle": "@nature", "confidence": 0.99,
                 "verification_url": "https://www.instagram.com/notnature/", "reason": "wrong handle"},
                {"entity": "Nature", "handle": "@nature", "confidence": 0.70,
                 "verification_url": "https://www.instagram.com/nature/", "reason": "low confidence"},
            ],
            "caption_text": "A paper worth reading.", "share_to_feed": True,
        })
        self.assertEqual(packet["mentions"], [])
        self.assertNotIn("@nature", packet["caption"])

    def test_no_distribution_metadata_still_yields_publishable_caption(self):
        packet = d.sanitize({
            "entities": [], "hashtags": [], "mentions": [],
            "caption_text": "Strong thesis without social metadata.", "share_to_feed": True,
        })
        self.assertEqual(packet["caption"], "Strong thesis without social metadata.")
        self.assertTrue(packet["share_to_feed"])

    def test_dry_packet_is_episode_specific(self):
        story = {
            "title": "Are sperm counts really collapsing?",
            "thesis": "The trend and its cause are separate questions.",
        }
        packet = d.build(story, live=False)
        self.assertIn("sperm counts", packet["caption"].lower())
        self.assertIn("#MensHealth", [x["tag"] for x in packet["hashtags"]])


if __name__ == "__main__":
    unittest.main()
