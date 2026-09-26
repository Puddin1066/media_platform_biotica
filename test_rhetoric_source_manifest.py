import unittest

import rhetoric_source_manifest as rsm


class RhetoricSourceManifestTests(unittest.TestCase):
    def test_manifest_is_valid_single_source_cohort(self):
        data = rsm.load_manifest()
        self.assertEqual(data["source_policy"], "huberman_lab_solo_only")
        self.assertEqual(len(data["episodes"]), 30)

    def test_cohort_balances_domain_fit_and_general_explanation(self):
        data = rsm.load_manifest()
        buckets = [ep["bucket"] for ep in data["episodes"]]
        self.assertEqual(buckets.count("mens_health_adjacent"), 15)
        self.assertEqual(buckets.count("explanatory_control"), 15)

    def test_every_source_is_official_episode_page(self):
        data = rsm.load_manifest()
        for ep in data["episodes"]:
            self.assertTrue(ep["url"].startswith("https://www.hubermanlab.com/episode/"))

    def test_manifest_contains_no_transcript_text(self):
        data = rsm.load_manifest()
        forbidden = {"transcript", "transcript_text", "source_text", "quote"}
        for ep in data["episodes"]:
            self.assertTrue(forbidden.isdisjoint(ep.keys()))


if __name__ == "__main__":
    unittest.main()
