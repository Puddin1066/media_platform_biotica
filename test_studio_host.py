import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "studio_module_runner", Path("studio/module_runner.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RUNNER = load_runner()


class StudioHostModuleTests(unittest.TestCase):
    def test_host_module_records_an_available_plate_without_generating_video(self):
        plates = [
            {"key": "satoshi/plates/seedance-a.mp4", "bytes": 6680000, "last_modified": ""},
            {"key": "satoshi/plates/seedance-b.mp4", "bytes": 11890000, "last_modified": ""},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(RUNNER, "ROOT", Path(tmp)), \
                 patch.object(RUNNER.media_store, "available_plates", return_value=plates), \
                 patch.object(RUNNER.media_store, "persist") as uploaded:
                first = RUNNER.run_host("games-episode", {"host": {}}, "", "")
                second = RUNNER.run_host("games-episode", {"host": {}}, "", "")
                manifest_path = Path(tmp) / "studio/episodes/games-episode/artifacts/host_manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            uploaded.assert_not_called()
        self.assertEqual(first, second)
        self.assertTrue(first[0].endswith("artifacts/host_manifest.json"))
        self.assertFalse(manifest["generated"])
        self.assertEqual(manifest["source"], "available")
        self.assertIn(manifest["plate"]["key"], {item["key"] for item in plates})

    def test_host_module_keeps_an_explicit_plate_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(RUNNER, "ROOT", Path(tmp)), \
                 patch.object(RUNNER.media_store, "available_plates") as listed:
                RUNNER.run_host("games-episode", {
                    "host": {"r2_key": "satoshi/plates/named.mp4"}
                }, "", "")
                manifest = json.loads((
                    Path(tmp) / "studio/episodes/games-episode/artifacts/host_manifest.json"
                ).read_text(encoding="utf-8"))
            listed.assert_not_called()
        self.assertEqual(manifest["source"], "explicit")
        self.assertEqual(manifest["plate"]["key"], "satoshi/plates/named.mp4")
        self.assertFalse(manifest["generated"])


if __name__ == "__main__":
    unittest.main()
