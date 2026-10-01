"""Offline checks for the durable Studio library and spend-free backlog plan."""
import json
import tempfile
import unittest
from pathlib import Path

import studio_library as library


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.episode = "sample-episode"
        self.workspace = self.root / "studio" / "episodes" / self.episode
        (self.workspace / "artifacts").mkdir(parents=True)
        (self.root / "studio" / "modules.json").write_text(json.dumps({
            "modules": [
                {"id": "source", "requires": []},
                {"id": "script", "requires": ["source"]},
                {"id": "voice", "requires": ["script"]},
                {"id": "assembly", "requires": ["script", "voice"]},
            ]
        }))
        (self.workspace / "request.json").write_text(json.dumps({
            "production": {"max_runway_credits": 900}
        }))
        self.manifest = {
            "episode_id": self.episode, "title": "A sample",
            "request_path": f"studio/episodes/{self.episode}/request.json",
            "modules": {
                "source": {"status": "completed", "version": 1},
                "script": {"status": "needs_review", "version": 1},
                "voice": {"status": "not_ready", "version": 0},
                "assembly": {"status": "not_ready", "version": 0},
            },
        }
        (self.workspace / "episode_manifest.json").write_text(json.dumps(self.manifest))

    def test_revisions_remain_addressable_and_gate_spend(self):
        script = self.workspace / "artifacts" / "script.txt"
        output = str(script.relative_to(self.root))
        script.write_text("First version.")
        library.capture(self.root, self.episode, self.manifest, "script", 1, [output])
        first = library._read(self.workspace / "library.json", {})["records"][0]
        script.write_text("A revised version.")
        library.capture(self.root, self.episode, self.manifest, "script", 2, [output])
        records = library._read(self.workspace / "library.json", {})["records"]
        self.assertEqual(len(records), 2)
        self.assertEqual((self.root / first["snapshot_path"]).read_text(), "First version.")
        self.assertNotEqual(records[0]["sha256"], records[1]["sha256"])
        plan = library.plan(self.root)["episodes"][0]
        self.assertEqual(plan["requires_review"], ["script"])
        self.assertEqual(plan["ready_to_dispatch"], [])
        self.assertFalse(plan["media_spend_authorized"])
        self.assertIsNone(plan["runway_credits_available"])

    def test_media_refs_and_archive_tamper_detection(self):
        voice = self.workspace / "artifacts" / "voice_manifest.json"
        voice.write_text(json.dumps({
            "takes": {"a": {"bucket": "media", "key": "voice/hash/take-a.wav",
                             "sha256": "a" * 64, "bytes": 100, "url": "https://example.org/a.wav"}}
        }))
        output = str(voice.relative_to(self.root))
        library.capture(self.root, self.episode, self.manifest, "voice", 1, [output])
        record = library._read(self.workspace / "library.json", {})["records"][0]
        self.assertEqual(record["media_refs"][0]["key"], "voice/hash/take-a.wav")
        (self.root / record["snapshot_path"]).write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "Archived artifact changed"):
            library.capture(self.root, self.episode, self.manifest, "voice", 1, [output])

    def test_backfill_current_outputs_without_media_calls(self):
        script = self.workspace / "artifacts" / "script.txt"
        script.write_text("An existing script.")
        self.manifest["modules"]["script"]["outputs"] = [str(script.relative_to(self.root))]
        (self.workspace / "episode_manifest.json").write_text(json.dumps(self.manifest))
        result = library.backfill(self.root)
        self.assertEqual(result["episodes"][0]["archived_records"], 1)
        self.assertEqual(result["episodes"][0]["legacy_records"], 1)
        self.assertTrue((self.root / "studio" / "library_index.json").exists())


if __name__ == "__main__":
    unittest.main()
