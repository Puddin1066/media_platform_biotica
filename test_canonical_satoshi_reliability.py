import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import canonical_satoshi_lipsync_runtime as runtime
import canonical_satoshi_runtime as base
import publish_satoshi_instagram as publisher


class CanonicalSatoshiReliabilityTests(unittest.TestCase):
    def test_avatar_uses_one_continuous_narration_master(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            narration = root / "generated" / "voice.wav"
            narration.parent.mkdir(parents=True)
            narration.write_bytes(b"voice")

            def collect(_record, target):
                Path(target).write_bytes(b"video")

            with patch.dict(os.environ, {"RUNWAY_AVATAR_ID": "avatar-1"}, clear=False), \
                 patch.object(runtime.runway_media, "submit_avatar", return_value={
                     "specification": {"avatar": "avatar-1", "audio": "voice.wav"},
                     "record": {"id": "job-1"},
                 }) as submit, \
                 patch.object(base, "_existing_runway_record", return_value=None), \
                 patch.object(base, "_wait_collect", side_effect=collect), \
                 patch.object(runtime.render_audio_guard, "validate", return_value={"ok": True}):
                result = runtime.ensure_continuous_host(
                    root, {}, {"host": {"mode": "avatar"}}, live=True
                )

            self.assertTrue(result["continuous"])
            self.assertTrue(result["file"].endswith("host-continuous.mp4"))
            # One dry specification check + one live submission, both against the
            # same continuous narration master. There are no per-beat avatar calls.
            self.assertEqual(submit.call_count, 2)
            self.assertTrue(all(Path(call.args[1]) == narration for call in submit.call_args_list))

    def test_canonical_identity_uses_request_episode_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            request = {
                "schema_version": 1,
                "trigger_phrase": "Run the Satoshi episode",
                "conversation_digest": {"source_messages": [
                    {"id": "u1", "speaker": "user", "text": "Digital health conversation"}
                ]},
                "editorial_mining": {
                    "interesting": [], "humorous": [], "insightful": [],
                    "contradictions": [], "objections": [], "claims_to_verify": []
                },
                "story_intent": {
                    "central_question": "What is the story?",
                    "provisional_thesis": "A thesis",
                    "mens_health_bridge": "A bridge"
                },
                "host": {"mode": "avatar"},
                "production": {"visual_mode": "openai_stills", "publish_instagram": True}
            }
            eid = base.episode_id(request)
            root = Path(tmp) / eid
            root.mkdir()
            (root / "request.json").write_text(json.dumps(request), encoding="utf-8")
            (root / "distribution.json").write_text(json.dumps({"episode_id": eid}), encoding="utf-8")
            self.assertEqual(runtime._assert_canonical_identity(root, {"title": "Fresh story"}), eid)

    def test_legacy_preview_workflow_cannot_publish(self):
        with patch.dict(os.environ, {"GITHUB_WORKFLOW": publisher.LEGACY_PREVIEW_WORKFLOW}, clear=False):
            with self.assertRaisesRegex(RuntimeError, "Legacy Satoshi preview workflow"):
                publisher.publish(
                    {"public_video_url": "https://example.com/reel.mp4"},
                    Path("unused.sqlite"), "token", "user"
                )


if __name__ == "__main__":
    unittest.main()
