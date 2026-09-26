import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import corpus_embeddings as ce
import corpus_namespace as cn


class CorpusNamespaceTests(unittest.TestCase):
    def test_source_family_and_mode_inference(self):
        self.assertEqual(cn.infer_source_family("huberman/episode-1.txt"), "huberman")
        self.assertEqual(cn.infer_mode("huberman"), "explanatory")
        self.assertEqual(cn.infer_source_family("last-week-tonight/story.md"), "lwt")
        self.assertEqual(cn.infer_mode("lwt"), "argumentative")
        self.assertEqual(cn.infer_source_family("revisionist-history/episode.txt"), "revisionist")
        self.assertEqual(cn.infer_mode("revisionist"), "discovery")

    def test_enrich_labels_adds_namespace(self):
        labels = {
            "primary_function": "mechanism",
            "secondary_functions": ["qualification"],
            "topic_tags": ["fertility"],
            "mechanics": "mechanism then caveat",
            "audience_stakes": "changes interpretation",
        }
        out = cn.enrich_labels(labels, "huberman/fertility.txt")
        self.assertEqual(out["source_family"], "huberman")
        self.assertEqual(out["mode"], "explanatory")

    def test_filter_happens_before_similarity_ranking(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "corpus.sqlite"
            with ce.connect(db_path) as db:
                rows = [
                    ("h", "huberman/a.txt", "Huberman", "huberman", "explanatory", [1.0, 0.0]),
                    ("l", "lwt/a.txt", "LWT", "lwt", "argumentative", [0.0, 1.0]),
                ]
                for cid, path, title, family, mode, vector in rows:
                    labels = {
                        "primary_function": "evidence",
                        "secondary_functions": [],
                        "topic_tags": [],
                        "mechanics": "x",
                        "audience_stakes": "y",
                        "source_family": family,
                        "mode": mode,
                    }
                    db.execute(
                        """INSERT INTO chunks
                        (id, source_path, source_title, chunk_index, text_sha256, text,
                         labels_json, retrieval_text, embedding_model, embedding_dimensions, embedding)
                        VALUES (?, ?, ?, 0, ?, '', ?, ?, ?, 2, ?)""",
                        (cid, path, title, cid, json.dumps(labels), "mechanics",
                         ce.DEFAULT_EMBED_MODEL, ce.pack_vector(vector)),
                    )
                db.commit()
            with mock.patch.dict(os.environ, {"OPENAI_LIVE_ENABLED": "true", "OPENAI_API_KEY": "test"}), \
                 mock.patch.object(ce, "embed_texts", return_value=[[1.0, 0.0]]):
                result = cn.search(db_path, "query", top_k=5, mode="argumentative", dimensions=2, live=True)
            self.assertEqual(len(result["results"]), 1)
            self.assertEqual(result["results"][0]["source_family"], "lwt")


if __name__ == "__main__":
    unittest.main()
