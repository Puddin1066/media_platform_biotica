import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schemas" / "satoshi_episode_request.schema.json"
EXAMPLE_PATH = ROOT / "requests" / "satoshi_episode" / "example.json"


class CanonicalEpisodeRequestContractTests(unittest.TestCase):
    def test_schema_and_example_are_valid_json(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["title"], "Canonical Satoshi Episode Request")
        self.assertEqual(example["schema_version"], 1)

    def test_example_is_conversation_first(self):
        example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(example["conversation_digest"]["source_messages"]), 1)
        self.assertIn("editorial_mining", example)
        self.assertIn("story_intent", example)
        self.assertEqual(example["production"]["visual_mode"], "openai_stills")

    def test_story_contract_requires_editorial_signals(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        required = set(schema["properties"]["editorial_mining"]["required"])
        self.assertTrue({
            "interesting",
            "humorous",
            "insightful",
            "contradictions",
            "objections",
            "claims_to_verify",
        }.issubset(required))

    def test_host_contract_allows_conversation_upload(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        modes = schema["properties"]["host"]["properties"]["mode"]["enum"]
        self.assertIn("conversation_upload", modes)
        self.assertIn("r2_plate", modes)
        self.assertIn("default_plate", modes)
        self.assertIn("avatar", modes)


if __name__ == "__main__":
    unittest.main()
