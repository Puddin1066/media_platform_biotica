"""Offline regression tests: no API credentials, paid calls, or network traffic."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from studio import compile_package, save_package, validate, FORMATS


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((Path(__file__).parent / "cases/mens-health.json").read_text())

    def test_all_formats_blocked(self):
        for name in FORMATS:
            result = compile_package(self.packet, name)
            self.assertFalse(result["publishable"])
            self.assertEqual(result["cost"]["api_calls"], 0)

    def test_idempotency(self):
        result = compile_package(self.packet, "short")
        with tempfile.TemporaryDirectory() as directory:
            first = save_package(result, directory)
            second = save_package(result, directory)
            self.assertEqual(first, second)
            self.assertEqual(len(list(Path(directory).iterdir())), 1)

    def test_revision_changes_identity(self):
        old = compile_package(self.packet, "podcast")
        self.packet["revision"] += 1
        self.assertNotEqual(old["run_id"], compile_package(self.packet, "podcast")["run_id"])

    def test_canon_changes_identity(self):
        old = compile_package(self.packet, "short")
        self.packet["canon"]["voice"] = "Another voice"
        self.assertNotEqual(old["run_id"], compile_package(self.packet, "short")["run_id"])

    def test_unknown_citation_rejected(self):
        self.packet["claims"] = [{"id": "c1", "type": "fact", "source_ids": ["missing"], "status": "verified"}]
        with self.assertRaises(ValueError):
            validate(self.packet)

    def test_pending_not_approved(self):
        self.packet["sources"] = [{"id": "s1", "url": "https://example.org"}]
        self.packet["claims"] = [{"id": "c1", "type": "fact", "source_ids": ["s1"], "status": "pending"}]
        self.assertEqual(compile_package(self.packet, "short")["approved_claims"], [])

    def test_verified_does_not_release(self):
        self.packet["sources"] = [{"id": "s1"}]
        self.packet["claims"] = [{"id": "c1", "type": "fact", "source_ids": ["s1"], "status": "verified"}]
        result = compile_package(self.packet, "short")
        self.assertEqual(len(result["approved_claims"]), 1)
        self.assertFalse(result["publishable"])

    def test_tampering_refuses_overwrite(self):
        result = compile_package(self.packet, "short")
        with tempfile.TemporaryDirectory() as directory:
            path = save_package(result, directory)
            path.write_text("changed")
            with self.assertRaises(ValueError):
                save_package(result, directory)

    def test_duplicate_sources_rejected(self):
        self.packet["sources"] = [{"id": "s1"}, {"id": "s1"}]
        with self.assertRaises(ValueError):
            validate(self.packet)

    def test_missing_revision_rejected(self):
        del self.packet["revision"]
        with self.assertRaises(ValueError):
            validate(self.packet)


if __name__ == "__main__":
    unittest.main()
