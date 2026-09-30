import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import satoshi_editorial_pipeline as editorial
import satoshi_production_pipeline as p


class SatoshiProductionPipelineTests(unittest.TestCase):
    def _fixture(self, tmp, regenerate=False):
        package = Path(tmp) / "package"
        package.mkdir()
        request = {
            "schema_version": 1,
            "trigger_phrase": "Run the Satoshi episode",
            "conversation_digest": {"summary": "x", "source_messages": [{"id": "u1", "speaker": "user", "text": "x"}]},
            "editorial_mining": {"interesting": [], "humorous": [], "insightful": [], "contradictions": [], "objections": [], "claims_to_verify": []},
            "story_intent": {"central_question": "q", "provisional_thesis": "t", "mens_health_bridge": "b"},
            "host": {"mode": "master_asset"},
            "production": {"visual_mode": "openai_stills", "publish_instagram": False},
        }
        request_path = Path(tmp) / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        script = {
            "title": "T",
            "thesis": "Thesis",
            "script": [
                {"sentence_id": f"s{i:02d}", "text": f"Sentence {i}.", "function": "evidence", "claim_status": "rhetorical", "citations": []}
                for i in range(1, 11)
            ],
            "visual_intents": [],
        }
        prosody = {"global_direction": "x", "sentences": [{"sentence_id": f"s{i:02d}"} for i in range(1, 11)]}
        audio = b"RIFF" + b"x" * 4096
        (package / "canonical_script.json").write_text(json.dumps(script), encoding="utf-8")
        (package / "performance_score.json").write_text(json.dumps(prosody), encoding="utf-8")
        (package / "visual_intents.json").write_text("[]", encoding="utf-8")
        (package / "narration").mkdir()
        (package / "narration" / "selected.wav").write_bytes(audio)
        manifest = {
            "status": "editorially_approved_with_audio_model_judge",
            "request_sha256": editorial.sha(request),
            "script_sha256": editorial.sha(script),
            "performance_sha256": editorial.sha(prosody),
            "audio_sha256": hashlib.sha256(audio).hexdigest(),
            "canonical_script": "canonical_script.json",
            "performance_score": "performance_score.json",
            "selected_audio": "narration/selected.wav",
            "visual_intents": "visual_intents.json",
            "audio_judge_requests_regeneration": regenerate,
        }
        (package / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return package, request_path, script

    def test_verify_package_accepts_matching_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, request_path, script = self._fixture(tmp)
            manifest, _, locked, _, audio = p.verify_package(package, request_path)
            self.assertEqual(locked, script)
            self.assertEqual(manifest["audio_sha256"], p.file_sha(audio))

    def test_verify_package_blocks_regeneration_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            package, request_path, _ = self._fixture(tmp, regenerate=True)
            with self.assertRaisesRegex(ValueError, "requested regeneration"):
                p.verify_package(package, request_path)

    def test_locked_story_preserves_every_word_and_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, script = self._fixture(tmp)
            story = p.locked_story(script, [])
            source = " ".join(s["text"] for s in script["script"])
            rendered = " ".join(b["spoken_text"] for b in story["beats"])
            self.assertEqual(source, rendered)
            self.assertEqual(len(story["beats"]), 10)

    def test_locked_story_rejects_too_few_sentences(self):
        script = {"title": "x", "script": [{"sentence_id": "s01", "text": "Only one."}]}
        with self.assertRaisesRegex(ValueError, "at least 10 sentences"):
            p.locked_story(script, [])


if __name__ == "__main__":
    unittest.main()
