import unittest

import rhetoric_benchmark as rb


class RhetoricBenchmarkTests(unittest.TestCase):
    def test_curated_library_is_small_and_structured(self):
        data = rb.load_curated()
        self.assertGreaterEqual(len(data["entries"]), 10)
        self.assertLessEqual(len(data["entries"]), 150)
        self.assertTrue(all(e["mechanic"] for e in data["entries"]))

    def test_manifest_compares_same_topic_across_all_arms(self):
        manifest = rb.benchmark_manifest(["Are sperm counts collapsing?"])
        self.assertEqual(len(manifest["candidates"]), 3)
        self.assertEqual({c["arm"] for c in manifest["candidates"]}, set(rb.ARMS))
        self.assertEqual({c["topic_id"] for c in manifest["candidates"]}, {"T001"})

    def test_scores_require_all_quality_dimensions(self):
        manifest = rb.benchmark_manifest(["Does TRT suppress fertility?"])
        score = {"candidate_id": "T001-curated"}
        for dimension in rb.DIMENSIONS:
            score[dimension] = 4
        self.assertTrue(rb.validate_scores(manifest, [score]))

    def test_summary_keeps_arms_separate(self):
        manifest = rb.benchmark_manifest(["Do testosterone ranges hide age effects?"])
        scores = []
        for candidate in manifest["candidates"]:
            score = {"candidate_id": candidate["candidate_id"]}
            for dimension in rb.DIMENSIONS:
                score[dimension] = 5 if candidate["arm"] == "curated" else 3
            scores.append(score)
        result = rb.summarize(manifest, scores)
        self.assertEqual(result["curated"]["hook_strength"], 5.0)
        self.assertEqual(result["none"]["hook_strength"], 3.0)


if __name__ == "__main__":
    unittest.main()
