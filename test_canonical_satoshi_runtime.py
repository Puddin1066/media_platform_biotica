import json
import tempfile
import unittest
from pathlib import Path

import canonical_satoshi_runtime as runtime


def request_fixture():
    def moment(text, score=0.9):
        return {"source_message_ids": ["m1"], "text": text, "score": score,
                "why_it_matters": "fixture"}
    return {
        "schema_version": 1,
        "trigger_phrase": "Run the Satoshi script",
        "conversation_digest": {
            "summary": "A long conversation discovered a better story than the opening question.",
            "source_messages": [
                {"id": "m1", "speaker": "user", "text": "The contradiction is more interesting than the headline."},
                {"id": "m2", "speaker": "assistant", "text": "That gives us an objection and a receipt to verify."},
            ],
        },
        "editorial_mining": {
            "interesting": [moment("The contradiction is more interesting than the headline.")],
            "humorous": [moment("Good story. Higher bar.", 0.8)],
            "insightful": [moment("The discriminating test matters more than the branding.")],
            "contradictions": [moment("The marketing claim and measurement class do not line up.")],
            "objections": [moment("A narrower intended use could still make the technology useful.")],
            "memorable_phrasing": [moment("Different physics, different lies you can tell.")],
            "claims_to_verify": ["A consequential factual claim requires verification."],
        },
        "story_intent": {
            "central_question": "What is actually interesting here?",
            "provisional_thesis": "Validation and intended use matter more than modality theater.",
            "mens_health_bridge": "Diagnostic quality changes decisions men make about fertility and health.",
            "must_keep_lines": ["Different physics, different lies you can tell."],
            "avoid": ["medical advice"],
        },
        "host": {"mode": "avatar"},
        "production": {
            "visual_mode": "openai_stills",
            "publish_instagram": False,
            "target_seconds": 35,
            "max_openai_usd": 2.0,
            "max_runway_credits": 700,
        },
    }


class CanonicalRuntimeTests(unittest.TestCase):
    def test_request_requires_conversation_not_topic_only(self):
        request = request_fixture()
        request["conversation_digest"]["source_messages"] = []
        with self.assertRaisesRegex(ValueError, "topic-only"):
            runtime.validate_request(request)

    def test_request_requires_openai_stills(self):
        request = request_fixture()
        request["production"]["visual_mode"] = "commons"
        with self.assertRaisesRegex(ValueError, "OpenAI stills"):
            runtime.validate_request(request)

    def test_dry_story_keeps_ten_editorial_roles(self):
        request = runtime.validate_request(request_fixture())
        story = runtime.build_story(request, live=False)
        self.assertEqual(runtime.STORY_ROLES, [beat["role"] for beat in story["beats"]])
        self.assertEqual("rhetorical", story["beats"][0]["claim_status"])
        self.assertIn("Higher bar", story["beats"][-1]["spoken_text"])

    def test_media_compiler_preserves_rich_story_roles(self):
        request = runtime.validate_request(request_fixture())
        story = runtime.build_story(request, live=False)
        production = runtime.compile_production(story)
        self.assertEqual(runtime.PRODUCTION_BEATS, [beat["cue_id"] for beat in production])
        self.assertEqual(["hook", "baseline_belief"], production[0]["story_roles"])
        self.assertEqual(["synthesis", "button"], production[-1]["story_roles"])
        self.assertEqual(10, sum(len(beat["story_roles"]) for beat in production))

    def test_episode_id_is_deterministic_and_conversation_sensitive(self):
        first = request_fixture()
        second = request_fixture()
        self.assertEqual(runtime.episode_id(first), runtime.episode_id(second))
        second["conversation_digest"]["source_messages"][0]["text"] += " New thought."
        self.assertNotEqual(runtime.episode_id(first), runtime.episode_id(second))

    def test_dry_run_writes_auditable_manifest_without_provider_calls(self):
        request = request_fixture()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "request.json"
            path.write_text(json.dumps(request), encoding="utf-8")
            result = runtime.run(path, output=Path(temp) / "out", live=False)
            self.assertEqual("planned", result["status"])
            root = Path(temp) / "out" / result["episode_id"]
            self.assertTrue((root / "request.json").is_file())
            self.assertTrue((root / "story.json").is_file())
            self.assertTrue((root / "production-beats.json").is_file())
            self.assertTrue((root / "storyboard.json").is_file())
            self.assertTrue((root / "manifest.json").is_file())
            still_plans = list((root / "generated" / "stills").glob("*.json"))
            self.assertEqual(10, len(still_plans))


if __name__ == "__main__":
    unittest.main()
