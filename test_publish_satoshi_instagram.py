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

    @patch.dict('os.environ', {'GITHUB_WORKFLOW': 'Produce Satoshi Episode'})
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
            }, clear=False), patch.object(pub, 'assert_publicly_fetchable', return_value=200), \
                    patch.object(pub.instagram, 'create_container',
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

    @patch.dict('os.environ', {'GITHUB_WORKFLOW': 'Produce Satoshi Episode'})
    def test_publish_fails_fast_on_container_error(self):
        release = {
            'status': 'approved_for_publication',
            'reviewer': 't', 'file': 'x', 'file_sha256': 'a' * 64,
            'public_video_url': 'https://media.example.org/r.mp4',
            'caption': 'c', 'script_sha256': 'b' * 64, 'footage_plan_sha256': 'c' * 64,
        }
        with patch.object(pub, 'assert_publicly_fetchable', return_value=200), \
             patch.object(pub.instagram, 'create_container',
                          return_value={'job': 'job1', 'state': 'container_created'}), \
             patch.object(pub.instagram, 'publish_container',
                          return_value={
                              'job': 'job1', 'state': 'failed', 'status_code': 'ERROR',
                              'provider_status': {'status_code': 'ERROR', 'status': 'bad url'},
                          }) as publish, \
             patch.object(pub.time, 'sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'container failed'):
                pub.publish(release, 'ledger.sqlite', 'token', '123')
        publish.assert_called_once()
        sleep.assert_not_called()

    @patch.dict('os.environ', {'GITHUB_WORKFLOW': 'Produce Satoshi Episode'})
    def test_publish_refuses_non_public_url_before_meta(self):
        release = {
            'status': 'approved_for_publication',
            'reviewer': 't', 'file': 'x', 'file_sha256': 'a' * 64,
            'public_video_url': 'https://acct.r2.cloudflarestorage.com/reel.mp4',
            'caption': 'c', 'script_sha256': 'b' * 64, 'footage_plan_sha256': 'c' * 64,
        }
        with patch.object(pub, 'assert_publicly_fetchable',
                          side_effect=ValueError('not anonymously fetchable')), \
             patch.object(pub.instagram, 'create_container') as create:
            with self.assertRaisesRegex(ValueError, 'not anonymously fetchable'):
                pub.publish(release, 'ledger.sqlite', 'token', '123')
        create.assert_not_called()

    def test_legacy_preview_cannot_publish(self):
        release = {'public_video_url': 'https://media.example.org/r.mp4'}
        with patch.dict('os.environ', {'GITHUB_WORKFLOW': 'Produce Satoshi Video Preview'}), patch.object(pub.instagram, 'create_container') as create:
            with self.assertRaisesRegex(RuntimeError, 'not permitted to publish'):
                pub.publish(release, 'ledger.sqlite', 'token', '123')
        create.assert_not_called()

    def test_default_poll_budget_is_under_four_minutes(self):
        import inspect
        source = inspect.getsource(pub.publish)
        self.assertIn('poll_seconds=5', source)
        self.assertIn('max_polls=36', source)


if __name__ == '__main__':
    unittest.main()
