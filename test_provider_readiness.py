import os
import unittest
from unittest.mock import patch

import media_store
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

    def test_video_rejects_r2_api_host_as_public_base(self):
        env = {
            "OPENAI_API_KEY": "x",
            "RUNWAYML_API_SECRET": "y",
            "RUNWAY_AVATAR_ID": "avatar",
            "R2_ACCOUNT_ID": "account",
            "R2_ACCESS_KEY_ID": "access",
            "R2_SECRET_ACCESS_KEY": "secret",
            "R2_BUCKET": "biotica-media",
            "MEDIA_PUBLIC_BASE_URL": "https://deae7b344f464f38bc4d337031db97c5.r2.cloudflarestorage.com",
        }
        with patch.dict(os.environ, env, clear=True):
            result = provider_readiness.check("video_preview")
        self.assertFalse(result["ready"])
        self.assertIn("MEDIA_PUBLIC_BASE_URL", result["invalid"])

    def test_instagram_publish_requires_meta_token_and_ig_user(self):
        with patch.dict(os.environ, {}, clear=True):
            missing = provider_readiness.check("instagram_publish")
        self.assertFalse(missing["ready"])
        self.assertEqual(
            missing["missing"],
            ["META_ACCESS_TOKEN", "IG_USER_ID", "MEDIA_PUBLIC_BASE_URL"],
        )
        with patch.dict(os.environ, {
            "META_ACCESS_TOKEN": "token",
            "IG_USER_ID": "123",
            "MEDIA_PUBLIC_BASE_URL": "https://media.example.com",
        }, clear=True):
            ready = provider_readiness.check("instagram_publish")
        self.assertTrue(ready["ready"])


class MediaPublicBaseTests(unittest.TestCase):
    def test_accepts_custom_public_domain(self):
        with patch.dict(os.environ, {
            "MEDIA_PUBLIC_BASE_URL": "https://media.example.com/cdn/",
        }, clear=False):
            self.assertEqual(media_store.public_base_url(), "https://media.example.com/cdn")

    def test_rejects_s3_api_host(self):
        with patch.dict(os.environ, {
            "MEDIA_PUBLIC_BASE_URL": "https://abc.r2.cloudflarestorage.com",
        }, clear=False):
            with self.assertRaisesRegex(ValueError, "must not be the R2 S3 API host"):
                media_store.public_base_url()


if __name__ == "__main__":
    unittest.main()
