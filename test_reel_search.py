"""Offline tests for systematic Reel lead search and short-recording gate."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import instagram
import reel_search


class HashtagDerivationTests(unittest.TestCase):
    def test_topic_yields_compact_hashtags(self):
        tags = reel_search.hashtags_for_topic('penile fracture', extra_tags=['menshealth'])
        self.assertIn('penilefracture', tags)
        self.assertIn('penile', tags)
        self.assertIn('fracture', tags)
        self.assertIn('menshealth', tags)


class ReelSearchTests(unittest.TestCase):
    def test_search_ranks_and_builds_record_queue(self):
        def fake_discover(tag, ig_user_id, token, version='v25.0', edge='top_media'):
            rows = {
                'penilefracture': [
                    {'id': 'instagram:1', 'provider': 'instagram', 'title': 'low',
                     'page_url': 'https://www.instagram.com/reel/1', 'direct_url': None,
                     'rights_status': 'creator_permission_needed', 'tag': tag,
                     'engagement': {'scope': 'hashtag_top_media', 'like_count': 2,
                                    'comments_count': 0, 'rank_score': 2, 'note': ''}},
                    {'id': 'instagram:2', 'provider': 'instagram', 'title': 'high',
                     'page_url': 'https://www.instagram.com/reel/2', 'direct_url': None,
                     'rights_status': 'creator_permission_needed', 'tag': tag,
                     'engagement': {'scope': 'hashtag_top_media', 'like_count': 100,
                                    'comments_count': 4, 'rank_score': 120, 'note': ''}},
                ],
            }.get(tag, [])
            return {'tag': tag, 'edge': edge, 'candidates': rows}

        with patch.object(instagram, 'discover_hashtag', side_effect=fake_discover):
            result = reel_search.search_reels(
                'penile fracture', 'ig-user', 'token', cue_id='evidence',
                tags=['penilefracture'], limit=10, account='byoticallc')
        self.assertEqual(result['account'], 'byoticallc')
        self.assertEqual(result['record_queue'][0]['candidate_id'], 'instagram:2')
        self.assertEqual(result['record_queue'][0]['rank_score'], 120)
        self.assertTrue(result['record_queue'][0]['record_to'].endswith('.mov'))
        self.assertIsNone(result['candidates'][0]['direct_url'])

    def test_accept_recordings_keeps_only_short_files(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            short = root / 'instagram_1.mov'
            long = root / 'instagram_2.mov'
            short.write_bytes(b'fake')
            long.write_bytes(b'fake')
            queue = {
                'topic': 'penile fracture',
                'account': 'byoticallc',
                'cue_id': 'evidence',
                'record_queue': [
                    {'candidate_id': 'instagram:1', 'record_to': 'clips/instagram_1.mov',
                     'permalink': 'https://www.instagram.com/reel/1', 'title': 'a',
                     'like_count': 10, 'comments_count': 1, 'rank_score': 15},
                    {'candidate_id': 'instagram:2', 'record_to': 'clips/instagram_2.mov',
                     'permalink': 'https://www.instagram.com/reel/2', 'title': 'b',
                     'like_count': 99, 'comments_count': 1, 'rank_score': 104},
                ],
            }

            def fake_probe(path):
                return 8.0 if path.name.endswith('1.mov') else 14.0

            with patch.object(reel_search, 'probe_duration', side_effect=fake_probe):
                accepted = reel_search.accept_recordings(queue, root, max_source_seconds=10)
            self.assertEqual(len(accepted['accepted']), 1)
            self.assertEqual(accepted['accepted'][0]['candidate_id'], 'instagram:1')
            self.assertEqual(accepted['rejected'][0]['reason'], 'too_long')
            catalog = reel_search.catalog_from_accepted(accepted)
            self.assertEqual(catalog['cue_id'], 'evidence')
            self.assertEqual(catalog['candidates'][0]['media_path'],
                             accepted['accepted'][0]['path'])


class InstagramDiscoverFieldsTests(unittest.TestCase):
    def test_discover_requests_engagement_fields_and_scores(self):
        calls = []

        def fake_graph(method, path, token, params=None, version='v25.0'):
            calls.append((method, path, params))
            if path == 'ig_hashtag_search':
                return {'data': [{'id': 'tag123'}]}
            return {'data': [
                {'id': 'post1', 'media_type': 'VIDEO', 'permalink': 'https://x/1',
                 'like_count': 10, 'comments_count': 2, 'caption': 'one'},
                {'id': 'post2', 'media_type': 'IMAGE', 'permalink': 'https://x/2',
                 'like_count': 999, 'comments_count': 9},
                {'id': 'post3', 'media_type': 'VIDEO', 'permalink': 'https://x/3',
                 'like_count': 50, 'comments_count': 1, 'caption': 'hot'},
            ]}

        with patch.object(instagram, 'graph', side_effect=fake_graph):
            result = instagram.discover_hashtag('device', 'owner', 'token')
        self.assertIn('like_count', calls[1][2]['fields'])
        self.assertEqual([c['id'] for c in result['candidates']],
                         ['instagram:post3', 'instagram:post1'])
        self.assertEqual(result['candidates'][0]['engagement']['rank_score'], 55)


if __name__ == '__main__':
    unittest.main()
