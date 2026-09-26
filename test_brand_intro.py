import unittest

import brand_intro


class BrandIntroTests(unittest.TestCase):
    def test_same_script_and_episode_are_stable(self):
        sha = "a" * 64
        first = brand_intro.spec(sha, "Testosterone testing conflict")
        second = brand_intro.spec(sha, "Testosterone testing conflict")
        self.assertEqual(first, second)

    def test_brand_is_fixed_but_episode_context_changes(self):
        sha = "b" * 64
        first = brand_intro.spec(sha, "Testosterone testing conflict")
        second = brand_intro.spec(sha, "Sperm count decline")
        self.assertEqual(first["brand"], second["brand"])
        self.assertEqual(first["host"], second["host"])
        self.assertEqual(first["variant"], second["variant"])
        self.assertEqual(first["case_id"], second["case_id"])
        self.assertNotEqual(first["episode_label"], second["episode_label"])

    def test_full_reveal_lands_after_hook(self):
        value = brand_intro.validate(brand_intro.spec("c" * 64, "A test headline"))
        self.assertGreaterEqual(value["start_frame"], 120)
        self.assertLessEqual(value["start_frame"], 210)
        self.assertLessEqual(value["duration_frames"], 60)
        self.assertEqual(value["brand"], "BIOTICA MEDIA")
        self.assertEqual(value["host"], "SATOSHI SHKRELI")
        self.assertEqual(value["bug_start_frame"], 0)
        self.assertEqual(value["case_id"], "CCCCCC")

    def test_episode_label_is_bounded(self):
        value = brand_intro.spec("d" * 64, "x" * 100)
        self.assertEqual(len(value["episode_label"]), 52)

    def test_variants_are_bounded(self):
        found = {brand_intro.spec((f"{i:02x}" * 32))["variant"] for i in range(32)}
        self.assertTrue(found.issubset(set(brand_intro.VARIANTS)))
        self.assertGreaterEqual(len(found), 2)


if __name__ == "__main__":
    unittest.main()
