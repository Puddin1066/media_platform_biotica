"""Tests for gated Instagram release packet helper."""
import json
import tempfile
import unittest
from pathlib import Path

import release_instagram


class ReleaseInstagramTests(unittest.TestCase):
    def test_build_and_validate_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            movie = root / 'reel.mp4'
            movie.write_bytes(b'fictional-reel-bytes')
            release = release_instagram.build_release(
                str(movie),
                'https://media.example.org/reel.mp4',
                'Fictional caption',
                'Owner',
                'script-hash',
                'plan-hash',
            )
            self.assertEqual(release['status'], 'approved_for_publication')
            self.assertEqual(release['file_sha256'], release_instagram.file_sha256(movie))
            ok = release_instagram.validate_release_packet(release)
            self.assertTrue(ok['ok'])

    def test_validate_rejects_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            movie = root / 'reel.mp4'
            movie.write_bytes(b'fictional-reel-bytes')
            release = release_instagram.build_release(
                str(movie),
                'https://media.example.org/reel.mp4',
                'Fictional caption',
                'Owner',
                'script-hash',
                'plan-hash',
            )
            release['file_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'file_sha256'):
                release_instagram.validate_release_packet(release)


if __name__ == '__main__':
    unittest.main()
