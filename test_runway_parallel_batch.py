import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runway_parallel_batch


class RunwayParallelBatchTests(unittest.TestCase):
    def test_tetris_manifest_compiles_under_cap(self):
        manifest = runway_parallel_batch.load_manifest(
            "production_specs/tetris_runway_parallel.json"
        )
        self.assertEqual(len(manifest["jobs"]), 8)
        self.assertEqual(
            sum(job["estimated_credits"] for job in manifest["jobs"]),
            165,
        )
        self.assertLessEqual(
            manifest["first_pass_estimated_credits"],
            manifest["max_credits"],
        )
        self.assertEqual(
            {job["model"] for job in manifest["jobs"]},
            {"seedance2_5", "wan3", "muse_image"},
        )

    def test_dry_run_makes_no_provider_call(self):
        with tempfile.TemporaryDirectory() as directory, patch(
            "runway_operation.api"
        ) as api:
            result = runway_parallel_batch.run(
                "production_specs/tetris_runway_parallel.json",
                Path(directory),
                live=False,
            )
            self.assertEqual(result["status"], "validated")
            self.assertEqual(result["parallel_jobs"], 8)
            self.assertEqual(result["first_pass_estimated_credits"], 165)
            api.assert_not_called()

    def test_request_ids_are_stable_and_unique(self):
        manifest = runway_parallel_batch.load_manifest(
            "production_specs/tetris_runway_parallel.json"
        )
        ids = [
            runway_parallel_batch.compile_request(job)["request_id"]
            for job in manifest["jobs"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(len(value) == 32 for value in ids))


if __name__ == "__main__":
    unittest.main()
