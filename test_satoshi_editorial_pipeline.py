import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import satoshi_editorial_pipeline as p


class SatoshiEditorialPipelineTests(unittest.TestCase):
    def test_normalize_source_requires_messages(self):
        with self.assertRaises(ValueError):
            p.normalize_source({"conversation_digest": {"source_messages": []}})

    def test_normalize_source_preserves_intent_and_target(self):
        request = {
            "conversation_digest": {"summary": "x", "source_messages": [{"id": "1", "speaker": "user", "text": "hi"}]},
            "editorial_mining": {"interesting": []},
            "story_intent": {"central_question": "q"},
            "production": {"target_seconds": 75},
        }
        out = p.normalize_source(request)
        self.assertEqual(out["story_intent"]["central_question"], "q")
        self.assertEqual(out["episode_constraints"]["target_seconds"], 75)

    def test_prosody_must_cover_locked_sentence_ids(self):
        locked = {"script": [{"sentence_id": "s01", "text": "A"}, {"sentence_id": "s02", "text": "B"}]}
        with patch.object(p, "_json_call", return_value={"sentences": [{"sentence_id": "s01"}] }):
            with self.assertRaises(ValueError):
                p.prosody_director("k", "m", locked)

    def test_audio_qa_selects_valid_take_closest_to_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.wav"; a.write_bytes(b"x" * 2048)
            b = Path(tmp) / "b.wav"; b.write_bytes(b"x" * 2048)
            with patch.object(p, "duration", side_effect=lambda x: 50.0 if Path(x) == a else 61.0):
                result = p.audio_qa({"a": a, "b": b}, 60)
            self.assertEqual(result["selected"], "b")
            self.assertEqual(result["selection_mode"], "mechanical_duration_qa")


if __name__ == "__main__":
    unittest.main()
