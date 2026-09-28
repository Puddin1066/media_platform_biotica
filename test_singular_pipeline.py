import os
import tempfile
import unittest
from unittest import mock

import chat_request
import rhetoric_retrieval
import speech_provider


class SingularPipelineTests(unittest.TestCase):
    def test_chat_request_preserves_conversational_inputs(self):
        resolved = chat_request.resolve({
            "topic": "TRT cardiovascular risk",
            "core_thesis": "The warning changed after better evidence.",
            "candidate_lines": ["The apocalypse missed its earnings call."],
            "suspicions": ["institutional certainty outran evidence"],
            "historical_analogies": ["Theranos"],
            "claims_to_verify": ["FDA changed the boxed warning in 2025"],
            "supplied_urls": ["https://example.com/source"],
        })
        self.assertEqual(resolved["schema_version"], 2)
        brief = resolved["creative_brief"]
        self.assertEqual(brief["core_thesis"], "The warning changed after better evidence.")
        self.assertEqual(brief["candidate_lines"], ["The apocalypse missed its earnings call."])
        self.assertEqual(brief["historical_analogies"], ["Theranos"])
        self.assertEqual(brief["claims_to_verify"], ["FDA changed the boxed warning in 2025"])

    def test_speech_provider_auto_falls_back_without_elevenlabs(self):
        with mock.patch.dict(os.environ, {"SATOSHI_SPEECH_PROVIDER": "auto"}, clear=True):
            self.assertEqual(speech_provider.selected_provider(), "runway")

    def test_speech_provider_auto_prefers_configured_elevenlabs(self):
        with mock.patch.dict(os.environ, {
            "SATOSHI_SPEECH_PROVIDER": "auto",
            "ELEVENLABS_API_KEY": "x",
            "ELEVENLABS_VOICE_ID": "voice",
        }, clear=True):
            self.assertEqual(speech_provider.selected_provider(), "elevenlabs")

    def test_character_alignment_compiles_word_times(self):
        words = speech_provider._word_timings({
            "characters": list("Hi all"),
            "character_start_times_seconds": [0, .1, .2, .3, .4, .5],
            "character_end_times_seconds": [.1, .2, .3, .4, .5, .6],
        })
        self.assertEqual([w["text"] for w in words], ["Hi", "all"])
        self.assertEqual(words[1]["start"], .3)

    def test_embedding_retrieval_cleanly_falls_back_without_private_db(self):
        with mock.patch.dict(os.environ, {"SATOSHI_CORPUS_DB": "/missing/corpus.sqlite"}, clear=True):
            self.assertEqual(rhetoric_retrieval.semantic_mechanics({"question": "test"}, "explanatory"), [])


if __name__ == "__main__":
    unittest.main()
