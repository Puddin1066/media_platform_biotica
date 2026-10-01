import os
import unittest
from unittest.mock import patch

import openai_models


class OpenAIModelPolicyTests(unittest.TestCase):
    def test_default_roles_cover_studio_jobs(self):
        roles = openai_models.roles()
        self.assertEqual(
            set(roles),
            {"editorial_reasoning", "research", "story", "script", "writing", "classification", "embedding"},
        )
        self.assertEqual(roles["editorial_reasoning"].model, "gpt-5.6-sol")
        self.assertEqual(roles["research"].model, "gpt-5.6-terra")
        self.assertEqual(roles["story"].model, "gpt-5.6-terra")
        self.assertEqual(roles["script"].model, "gpt-5.6-terra")
        self.assertEqual(roles["classification"].model, "gpt-5.6-luna")
        self.assertEqual(roles["embedding"].model, "text-embedding-3-small")

    def test_environment_override_is_respected(self):
        with patch.dict(os.environ, {"OPENAI_WRITING_MODEL": "custom-model"}, clear=False):
            self.assertEqual(openai_models.model_for("writing"), "custom-model")
            self.assertEqual(openai_models.model_for("story"), "custom-model")
            self.assertEqual(openai_models.model_for("script"), "custom-model")

    def test_story_and_script_can_be_tuned_independently(self):
        with patch.dict(os.environ, {
            "OPENAI_STORY_MODEL": "story-model",
            "OPENAI_SCRIPT_MODEL": "script-model",
            "OPENAI_STORY_REASONING": "high",
            "OPENAI_SCRIPT_REASONING": "low",
        }, clear=False):
            self.assertEqual(openai_models.model_for("story"), "story-model")
            self.assertEqual(openai_models.model_for("script"), "script-model")
            self.assertEqual(openai_models.reasoning_for("story"), "high")
            self.assertEqual(openai_models.reasoning_for("script"), "low")

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
