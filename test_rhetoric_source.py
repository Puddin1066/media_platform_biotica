import json
import unittest
from pathlib import Path

import rhetoric_source as rs


class RhetoricSourceTests(unittest.TestCase):
    def test_repo_policy_is_single_source_huberman_solo(self):
        policy = rs.validate_policy(rs.load_json(rs.POLICY_PATH))
        self.assertEqual(policy["canonical_source"]["name"], "Huberman Lab solo episodes")
        self.assertEqual(policy["canonical_source"]["allowed_content"], ["solo_explanatory_episode"])
        self.assertFalse(policy["runtime_rules"]["raw_transcript_in_prompt"])
        self.assertFalse(policy["runtime_rules"]["creator_voice_imitation"])
        self.assertTrue(policy["runtime_rules"]["derived_mechanics_only"])

    def test_mixed_source_policy_is_rejected(self):
        policy = rs.load_json(rs.POLICY_PATH)
        policy["source_policy"] = "multi_source"
        with self.assertRaisesRegex(ValueError, "single_source"):
            rs.validate_policy(policy)

    def test_promoted_mechanic_requires_huberman_episode_provenance(self):
        library = {
            "entries": [{
                "id": "x",
                "mechanic": "Neutral structural move",
                "provenance": {
                    "source_family": "ted",
                    "episode_ids": ["ep-1"],
                    "contains_source_prose": False,
                },
            }]
        }
        with self.assertRaisesRegex(ValueError, "noncanonical source"):
            rs.validate_mechanics_library(library, require_promoted_provenance=True)

    def test_promoted_mechanic_rejects_source_prose(self):
        library = {
            "entries": [{
                "id": "x",
                "mechanic": "Neutral structural move",
                "provenance": {
                    "source_family": "huberman_lab_solo",
                    "episode_ids": ["ep-1"],
                    "contains_source_prose": True,
                },
            }]
        }
        with self.assertRaisesRegex(ValueError, "must not contain source prose"):
            rs.validate_mechanics_library(library, require_promoted_provenance=True)

    def test_current_seed_library_is_explicitly_bootstrap_only(self):
        library = rs.load_json(rs.MECHANICS_PATH)
        rs.validate_mechanics_library(library, require_promoted_provenance=False)
        self.assertEqual(
            library["promotion_status"],
            "bootstrap_only_pending_huberman_provenance_and_benchmark",
        )


if __name__ == "__main__":
    unittest.main()
