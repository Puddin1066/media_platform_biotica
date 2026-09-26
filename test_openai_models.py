import os
import unittest
from unittest.mock import patch

import openai_models


class OpenAIModelPolicyTests(unittest.TestCase):
    def test_default_roles_cover_studio_jobs(self):
        roles = openai_models.roles()
        self.assertEqual(
            set(roles),
            {"editorial_reasoning", "research", "writing", "classification", "embedding"},
        )
        self.assertEqual(roles["editorial_reasoning"].model, "gpt-5.6-sol")
        self.assertEqual(roles["research"].model, "gpt-5.6-terra")
        self.assertEqual(roles["classification"].model, "gpt-5.6-luna")
        self.assertEqual(roles["embedding"].model, "text-embedding-3-small")

    def test_environment_override_is_respected(self):
        with patch.dict(os.environ, {"OPENAI_WRITING_MODEL": "custom-model"}, clear=False):
            self.assertEqual(openai_models.model_for("writing"), "custom-model")

    def test_public_config_never_contains_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "secret-test-key"}, clear=False):
            config = str(openai_models.public_config())
            self.assertNotIn("secret-test-key", config)
            self.assertNotIn("OPENAI_API_KEY", config)

    def test_unknown_role_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "Unknown OpenAI model role"):
            openai_models.model_for("magic")


if __name__ == "__main__":
    unittest.main()
