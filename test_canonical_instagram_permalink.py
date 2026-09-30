import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import canonical_instagram_permalink as permalink


class CanonicalInstagramPermalinkTests(unittest.TestCase):
    def packet(self):
        return {
            "status": "published",
            "result": {"publish": {"media_id": "17890000000000000", "state": "published"}},
        }

    def test_resolve_requires_real_instagram_permalink(self):
        with patch.object(permalink.instagram, "graph", return_value={
            "id": "17890000000000000",
            "permalink": "https://www.instagram.com/reel/ABC123/",
            "media_type": "VIDEO",
        }) as graph:
            result = permalink.resolve(self.packet(), "token")
        self.assertEqual(result["permalink"], "https://www.instagram.com/reel/ABC123/")
        self.assertTrue(result["verified"])
        graph.assert_called_once_with(
            "GET", "17890000000000000", "token",
            {"fields": "id,permalink,media_type,timestamp"}, "v25.0",
        )

    def test_missing_permalink_fails_closed(self):
        with patch.object(permalink.instagram, "graph", return_value={
            "id": "17890000000000000", "media_type": "VIDEO",
        }):
            with self.assertRaisesRegex(RuntimeError, "valid Instagram permalink"):
                permalink.resolve(self.packet(), "token")

    def test_enrich_file_persists_operator_link(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "instagram.json"
            path.write_text(json.dumps(self.packet()), encoding="utf-8")
            with patch.object(permalink, "resolve", return_value={
                "media_id": "17890000000000000",
                "permalink": "https://www.instagram.com/reel/XYZ789/",
                "media_type": "VIDEO",
                "timestamp": "2026-09-29T23:00:00+0000",
                "verified": True,
            }):
                result = permalink.enrich_file(path, token="token")
            saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["permalink"], "https://www.instagram.com/reel/XYZ789/")
        self.assertEqual(saved["permalink"], result["permalink"])
        self.assertEqual(saved["result"]["permalink"], result["permalink"])
        self.assertTrue(saved["published_media"]["verified"])

    def test_find_publish_packet_uses_canonical_episode_output(self):
        with tempfile.TemporaryDirectory() as root:
            old = Path(root) / "episode-a" / "instagram.json"
            new = Path(root) / "episode-b" / "instagram.json"
            old.parent.mkdir(parents=True)
            new.parent.mkdir(parents=True)
            old.write_text("{}", encoding="utf-8")
            new.write_text("{}", encoding="utf-8")
            old.touch()
            new.touch()
            self.assertIn(permalink.find_publish_packet(root).name, {"instagram.json"})


if __name__ == "__main__":
    unittest.main()
