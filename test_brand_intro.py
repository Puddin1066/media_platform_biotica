import unittest

import brand_intro


class BrandIntroTests(unittest.TestCase):
    def test_same_script_hash_is_stable(self):
        sha = "a" * 64
        self.assertEqual(brand_intro.spec(sha), brand_intro.spec(sha))

    def test_full_reveal_lands_after_hook(self):
        value = brand_intro.validate(brand_intro.spec("b" * 64))
        self.assertGreaterEqual(value["start_frame"], 120)
        self.assertLessEqual(value["start_frame"], 210)
        self.assertLessEqual(value["duration_frames"], 60)
        self.assertEqual(value["brand"], "BIOTICA MEDIA")
        self.assertEqual(value["host"], "SATOSHI SHKRELI")
        self.assertEqual(value["bug_start_frame"], 0)

    def test_variants_are_bounded(self):
        found = {brand_intro.spec((f"{i:02x}" * 32))["variant"] for i in range(32)}
        self.assertTrue(found.issubset(set(brand_intro.VARIANTS)))
        self.assertGreaterEqual(len(found), 2)


if __name__ == "__main__":
    unittest.main()
