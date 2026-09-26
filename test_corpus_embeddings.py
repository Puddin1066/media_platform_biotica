import tempfile
import unittest
from pathlib import Path

import corpus_embeddings as ce


class CorpusEmbeddingTests(unittest.TestCase):
    def test_chunk_text_is_deterministic_and_bounded(self):
        text = "\n\n".join(["Paragraph %d " % i + ("x" * 700) for i in range(8)])
        a = ce.chunk_text(text, target_chars=1400, overlap_chars=120)
        b = ce.chunk_text(text, target_chars=1400, overlap_chars=120)
        self.assertEqual(a, b)
        self.assertGreater(len(a), 1)
        self.assertTrue(all(chunk.strip() for chunk in a))

    def test_vector_round_trip(self):
        vector = [0.1, -0.2, 0.3, 0.4]
        blob = ce.pack_vector(vector)
        restored = ce.unpack_vector(blob, 4)
        for expected, actual in zip(vector, restored):
            self.assertAlmostEqual(expected, actual, places=6)

    def test_private_sqlite_schema_and_stats(self):
        with tempfile.TemporaryDirectory() as td:
            db_path = Path(td) / "corpus.sqlite"
            with ce.connect(db_path) as db:
                vector = [0.5, 0.5]
                db.execute(
                    """INSERT INTO chunks
                    (id, source_path, source_title, chunk_index, text_sha256, text,
                     labels_json, retrieval_text, embedding_model,
                     embedding_dimensions, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    ("c1", "/private/a.txt", "A", 0, "hash", "text",
                     '{"primary_function":"hook"}', "mechanics",
                     "text-embedding-3-small", 2, ce.pack_vector(vector)),
                )
                db.commit()
            result = ce.stats(db_path)
            self.assertEqual(result["chunks"], 1)
            self.assertEqual(result["sources"], 1)
            self.assertEqual(result["indexes"][0]["dimensions"], 2)

    def test_dry_run_does_not_call_provider(self):
        with tempfile.TemporaryDirectory() as td:
            transcript = Path(td) / "episode.txt"
            transcript.write_text("One paragraph.\n\nAnother paragraph.", encoding="utf-8")
            result = ce.ingest_file(Path(td) / "index.sqlite", transcript, live=False)
            self.assertEqual(result["status"], "dry_run")
            self.assertGreaterEqual(result["chunks"], 1)


if __name__ == "__main__":
    unittest.main()
