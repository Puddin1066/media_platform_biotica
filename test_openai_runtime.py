import json
import unittest
from unittest import mock

import openai_runtime


class OpenAIRuntimeTests(unittest.TestCase):
    def test_credential_and_live_gate(self):
        with self.assertRaises(ValueError):
            openai_runtime.credential({})
        self.assertEqual(openai_runtime.credential({"OPENAI_API_KEY": " key "}), "key")
        with self.assertRaises(ValueError):
            openai_runtime.require_live({"OPENAI_API_KEY": "key"})
        self.assertEqual(
            openai_runtime.require_live({"OPENAI_API_KEY": "key", "OPENAI_LIVE_ENABLED": "true"}),
            "key",
        )

    def test_incomplete_status_includes_reason(self):
        result = {"status": "incomplete", "incomplete_details": {"reason": "max_output_tokens"}}
        with self.assertRaisesRegex(ValueError, "max_output_tokens"):
            openai_runtime.require_completed(result)

    def test_extracts_structured_text_and_returned_web_sources_without_annotations(self):
        result = {
            "status": "completed",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"sources": [{"url": "https://example.org/a", "title": "A"}]},
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps({"ok": True}), "annotations": []}],
                },
            ],
        }
        payload, sources = openai_runtime.extract_json(result)
        self.assertEqual(payload, {"ok": True})
        self.assertEqual(sources[0]["url"], "https://example.org/a")
        self.assertEqual(sources[0]["role"], "consulted")

    def test_preflight_checks_structured_output_and_sources(self):
        fixture = {
            "status": "completed",
            "model": "fixture-model",
            "id": "resp_fixture",
            "output": [
                {
                    "type": "web_search_call",
                    "action": {"sources": [{"url": "https://example.org/a", "title": "A"}]},
                },
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps({"ok": True, "diagnostic": "ok"}), "annotations": []}],
                },
            ],
        }
        with mock.patch("openai_runtime.call_responses", return_value=fixture) as call:
            result = openai_runtime.preflight("fixture-model", key="secret")
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source_count"], 1)
        body = call.call_args.args[0]
        self.assertEqual(body["max_tool_calls"], 1)
        self.assertEqual(body["text"]["format"]["type"], "json_schema")


if __name__ == "__main__":
    unittest.main()
