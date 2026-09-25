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

    def test_video_requires_all_provider_configuration(self):
        env = {
            "OPENAI_API_KEY": "x",
            "RUNWAYML_API_SECRET": "y",
            "RUNWAY_VOICE_ID": "voice",
            "RUNWAY_AVATAR_ID": "avatar",
        }
        with patch.dict(os.environ, env, clear=True):
            result = provider_readiness.check("video_preview")
        self.assertTrue(result["ready"])
        self.assertEqual(result["missing"], [])

if __name__ == "__main__":
    unittest.main()
