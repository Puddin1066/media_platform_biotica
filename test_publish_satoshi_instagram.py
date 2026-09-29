"""Tests for auto Instagram publish packet assembly (mocked Meta calls)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import publish_satoshi_instagram as pub
import release_instagram


class AutoPublishTests(unittest.TestCase):
    def test_find_public_url_by_checksum(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            video = root / 'reel.mp4'
            video.write_bytes(b'auto-publish-bytes')
            checksum = release_instagram.file_sha256(video)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'assets': [{'sha256': checksum,
                            'url': 'https://media.example.org/reel.mp4',
                            'key': 'satoshi/assets/ab/cd/reel.mp4'}]
            }), encoding='utf-8')
            url, key = pub.find_public_url(video, [manifest])
            self.assertEqual(url, 'https://media.example.org/reel.mp4')
            self.assertTrue(key.endswith('reel.mp4'))

    def test_dry_run_builds_release_without_meta(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            video = root / 'reel.mp4'
            video.write_bytes(b'auto-publish-bytes')
            checksum = release_instagram.file_sha256(video)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'assets': [{'sha256': checksum,
                            'url': 'https://media.example.org/reel.mp4'}]
            }), encoding='utf-8')
            request = root / 'request.json'
            request.write_text(json.dumps({'topic': 'TRT pilot'}), encoding='utf-8')
            draft = root / 'draft.json'
            draft.write_text(json.dumps({
                'script': {'title': 'A title', 'segments': [], 'open_question': 'q'}
            }), encoding='utf-8')
            result = pub.run(
                video, [manifest], request, draft, None,
                root / 'ledger.sqlite', live=False)
            self.assertEqual(result['status'], 'dry_run_ready')
            self.assertEqual(result['account'], 'byoticallc')
            self.assertEqual(result['release']['status'], 'approved_for_publication')

    def test_live_publish_uses_instagram_adapters(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            video = root / 'reel.mp4'
            video.write_bytes(b'auto-publish-bytes')
            checksum = release_instagram.file_sha256(video)
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({
                'assets': [{'sha256': checksum,
                            'url': 'https://media.example.org/reel.mp4'}]
            }), encoding='utf-8')
            with patch.dict('os.environ', {
                'META_ACCESS_TOKEN': 'token',
                'IG_USER_ID': '123',
            }, clear=False), patch.object(pub.instagram, 'create_container',
                                         return_value={'job': 'job1', 'state': 'container_created'}), \
                    patch.object(pub.instagram, 'publish_container',
                                 return_value={'job': 'job1', 'state': 'published', 'media_id': 'm1'}), \
                    patch.object(pub.instagram, 'insights',
                                 return_value={'job': 'job1', 'metrics': []}):
                result = pub.run(
                    video, [manifest], None, None, None,
                    root / 'ledger.sqlite', live=True)
            self.assertEqual(result['status'], 'published')
            self.assertEqual(result['result']['publish']['media_id'], 'm1')


if __name__ == '__main__':
    unittest.main()
