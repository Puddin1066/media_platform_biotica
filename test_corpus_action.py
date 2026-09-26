import tempfile
import unittest
from pathlib import Path

import corpus_action as ca
import corpus_embeddings as ce


class CorpusActionTests(unittest.TestCase):
    def test_safe_retrieval_text_excludes_source_passage(self):
        labels = {
            "primary_function": "mechanism",
            "secondary_functions": ["qualification"],
            "topic_tags": ["sleep"],
            "audience_stakes": "changes interpretation",
            "mechanics": "claim then caveat",
        }
        text = ca.safe_retrieval_text(labels)
        self.assertIn("claim then caveat", text)
        self.assertNotIn("source passage", text)

    def test_plan_skips_identical_chunk_hash_already_indexed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "transcripts"
            root.mkdir()
            transcript = root / "episode.txt"
            transcript.write_text("A sufficiently long paragraph about a mechanism. " * 30, encoding="utf-8")
            db_path = Path(td) / "runtime.sqlite"
            first = ca.build_plan(root, db_path, ce.DEFAULT_EMBED_MODEL, 8, target_chars=900, overlap_chars=100)
            self.assertGreater(first["planned_chunks"], 0)
            row = first["pending"][0]
            with ce.connect(db_path) as db:
                db.execute(
                    """INSERT INTO chunks
                    (id, source_path, source_title, chunk_index, text_sha256, text,
                     labels_json, retrieval_text, embedding_model, embedding_dimensions, embedding)
                    VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, ?, ?)""",
                    (row["id"], row["source_path"], row["source_title"], row["chunk_index"],
                     row["text_sha256"], '{"primary_function":"mechanism"}', "mechanics",
                     ce.DEFAULT_EMBED_MODEL, 8, ce.pack_vector([0.0] * 8)),
                )
                db.commit()
            second = ca.build_plan(root, db_path, ce.DEFAULT_EMBED_MODEL, 8, target_chars=900, overlap_chars=100)
            self.assertEqual(second["already_indexed"], 1)
            self.assertEqual(len(second["pending"]), second["planned_chunks"] - 1)

    def test_dry_run_never_requires_openai_key(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "transcripts"
            root.mkdir()
            (root / "episode.md").write_text("Paragraph one.\n\nParagraph two.", encoding="utf-8")
            result = ca.build(root, Path(td) / "runtime.sqlite", live=False)
            self.assertEqual(result["status"], "dry_run")
            self.assertGreaterEqual(result["planned_chunks"], 1)


if __name__ == "__main__":
    unittest.main()
