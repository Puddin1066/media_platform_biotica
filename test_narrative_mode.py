import os
import tempfile
import unittest
from pathlib import Path

import narrative_mode
import reference_corpus


class NarrativeModeTests(unittest.TestCase):
    def test_defaults_to_explanatory_for_plain_health_question(self):
        self.assertEqual(
            narrative_mode.choose_mode("Does sauna affect male fertility?"),
            "explanatory",
        )

    def test_argumentative_signals_select_argumentative(self):
        self.assertEqual(
            narrative_mode.choose_mode("Is testosterone marketing a scam?"),
            "argumentative",
        )

    def test_discovery_signals_select_discovery(self):
        self.assertEqual(
            narrative_mode.choose_mode("Why did male sperm counts change?", "history and mystery"),
            "discovery",
        )

    def test_explicit_override_wins(self):
        self.assertEqual(
            narrative_mode.choose_mode("plain topic", override="argumentative"),
            "argumentative",
        )

    def test_source_family_mapping(self):
        self.assertEqual(narrative_mode.source_family_for_mode("argumentative"), "lwt")
        self.assertEqual(narrative_mode.source_family_for_mode("explanatory"), "huberman")
        self.assertEqual(narrative_mode.source_family_for_mode("discovery"), "revisionist")

    def test_reference_selector_honors_runtime_mode_override(self):
        exemplars = [
            {"id": "a", "source_id": "lwt", "mode": "argumentative", "functions": ["hook"],
             "summary": "a", "mechanics": "a", "topic_tags": ["mens_health"], "rights_status": "derived"},
            {"id": "b", "source_id": "huberman", "mode": "explanatory", "functions": ["mechanism"],
             "summary": "b", "mechanics": "b", "topic_tags": ["mens_health"], "rights_status": "derived"},
        ]
        old = os.environ.get("SATOSHI_NARRATIVE_MODE")
        os.environ["SATOSHI_NARRATIVE_MODE"] = "explanatory"
        try:
            selected = reference_corpus.select_exemplars(exemplars, "argumentative", ["mens_health"], 3)
        finally:
            if old is None:
                os.environ.pop("SATOSHI_NARRATIVE_MODE", None)
            else:
                os.environ["SATOSHI_NARRATIVE_MODE"] = old
        self.assertEqual([row["id"] for row in selected], ["b"])


if __name__ == "__main__":
    unittest.main()
