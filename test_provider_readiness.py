import os
import unittest
from unittest.mock import patch
import provider_readiness

class ProviderReadinessTests(unittest.TestCase):
    def test_research_requires_openai(self):
        with patch.dict(os.environ, {}, clear=True):
            result = provider_readiness.check("research_script")
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing"], ["OPENAI_API_KEY"])

    def test_video_requires_runway_avatar_and_r2_storage(self):
        env = {
            "OPENAI_API_KEY": "x",
            "RUNWAYML_API_SECRET": "y",
            "RUNWAY_AVATAR_ID": "avatar",
            "R2_ACCOUNT_ID": "account",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_BUCKET": "biotica-media",
            "MEDIA_PUBLIC_BASE_URL": "https://media.example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            result = provider_readiness.check("video_preview")
        self.assertTrue(result["ready"])
        self.assertEqual(result["missing"], [])

if __name__ == "__main__":
    unittest.main()
