"""Offline contract tests for discovery metadata, rights and exact shot timing."""
import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import footage


class FootageTests(unittest.TestCase):
    def test_youtube_metadata_has_no_download_source(self):
        search = {'items': [{'id': {'videoId': 'abc123'}}]}
        detail = {'items': [{'id': 'abc123', 'snippet': {'title': 'Demo'},
                             'statistics': {'viewCount': '1000'},
                             'status': {'license': 'youtube'}}]}
        with patch.object(footage, 'fetch_json', side_effect=[search, detail]):
            row = footage.discover_youtube('topic', 'test-key')[0]
        self.assertIsNone(row['direct_url'])
        self.assertEqual(row['engagement']['scope'], 'whole_video')

    def test_best_retention_window(self):
        points = [{'second': sec, 'watch_ratio': ratio}
                  for sec, ratio in enumerate([.2, .3, .4, .9, .9, .9, .7])]
        self.assertEqual(footage.best_window(points, 3), (3, .9))

    def test_plan_requires_reviewed_rights_and_six_shots(self):
        with tempfile.TemporaryDirectory() as root:
            master = Path(root) / 'source.mp4'
            master.touch()
            catalog = {'topic': 'device', 'candidates': [{'id': 'youtube:abc'}]}
            approval = {'candidate_id': 'youtube:abc', 'media_source': str(master),
                        'license_basis': 'creator supplied source and cross-platform grant',
                        'credit': 'Creator A', 'rights_status': 'approved',
                        'start_seconds': 9, 'script_cue': 'show operating tip'}
            result = footage.plan(catalog, [approval] * 6)
            self.assertEqual([s['destination_seconds'] for s in result['shots']],
                             [0, 5, 10, 15, 20, 25])
            self.assertEqual(result['shots'][0]['selection_basis'], 'editor_selected')
            with self.assertRaises(ValueError):
                footage.plan(catalog, [{**approval, 'rights_status': 'pending'}] * 6)
            with self.assertRaises(ValueError):
                footage.plan(catalog, [approval] * 5)

    def test_never_pass_youtube_urls_to_renderer(self):
        for url in ('https://youtube.com/watch?v=x',
                    'https://r1.googlevideo.com/file.mp4', 'http://example.org/a.mp4'):
            with self.assertRaises(ValueError):
                footage.safe_media_source(url)

    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'FFmpeg required')
    def test_two_second_montage_and_avatar_overlay(self):
        """A short real render catches FFmpeg filter and concat mistakes."""
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source, host, output = (root / name for name in ('source.mp4', 'host.mp4', 'out.mp4'))
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            'testsrc2=size=320x180:rate=30', '-t', '3',
                            '-c:v', 'libx264', str(source)], check=True)
            subprocess.run(['ffmpeg', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            'color=c=blue:s=1080x1920:r=30', '-t', '2',
                            '-c:v', 'libx264', str(host)], check=True)
            catalog = {'topic': 'demo', 'candidates': [{'id': 'local:demo'}]}
            items = [{'candidate_id': 'local:demo', 'rights_status': 'approved',
                      'license_basis': 'self-created', 'credit': 'Biotica',
                      'media_source': str(source), 'start_seconds': sec}
                     for sec in (0, 1)]
            footage.render(footage.plan(catalog, items, 2, 1), output, host)
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                                     'format=duration', '-of', 'default=nw=1:nk=1',
                                     str(output)], check=True, capture_output=True, text=True)
            self.assertAlmostEqual(float(result.stdout.strip()), 2.0, places=1)


if __name__ == '__main__':
    unittest.main()
