"""Contract checks for orchestration without network or paid media calls."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import episode
from speech_timing import BEATS
from studio import digest


def fixture(root):
    root = Path(root)
    board = {'status': 'awaiting_footage', 'script_sha256': 'fictional',
             'cues': [{'cue_id': beat, 'spoken_text': 'Fictional narration.',
                       'claim_ids': ['fictional']} for beat in BEATS]}
    clip = root / 'clips' / 'creator.mp4'
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b'fictional')
    plan = {'status': 'renderable_not_publish_approved', 'script_sha256': 'fictional',
            'shots': [{'media_source': 'clips/creator.mp4',
                       'license_basis': 'Fictional fixture', 'credit': 'Fixture'}
                      for _ in range(6)]}
    (root / 'storyboard.json').write_text(json.dumps(board))
    (root / 'footage-plan.json').write_text(json.dumps(plan))
    return board, plan


class EpisodeTests(unittest.TestCase):
    def test_parallel_dry_run_and_existing_ledger_never_resubmits(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            result = episode.submit_audio(root, 'fixture-voice')
            self.assertEqual(list(result), list(BEATS))
            self.assertTrue(all(r['state'] == 'dry_run' for r in result.values()))
            spec = result['opening']['specification']
            record = root / 'generated' / 'runway' / (digest(spec) + '.json')
            record.parent.mkdir(parents=True)
            record.write_text(json.dumps({'state': 'reserved_unknown',
                                          'specification': spec}))
            with patch('episode.runway_media.client_from_environment',
                       side_effect=AssertionError('must not call provider')):
                again = episode.submit_audio(root, 'fixture-voice', live=False)
            self.assertEqual(again['opening']['state'], 'reserved_unknown')

    def test_source_escape_rejected_before_any_job(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'episode'
            root.mkdir()
            _, plan = fixture(root)
            plan['shots'][0]['media_source'] = '../outside.mp4'
            (root / 'footage-plan.json').write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'private relative'):
                episode.submit_audio(root, 'voice')

    def test_rerender_reuses_collected_host_without_provider(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            (root / 'generated').mkdir()
            (root / 'generated' / 'host.mp4').write_bytes(b'fictional')
            for beat in BEATS:
                file = root / 'audio' / (beat + '.wav')
                file.parent.mkdir(exist_ok=True)
                file.write_bytes(b'fictional')
            with patch('episode.production_job.prepare', return_value=Path('remotion/public/episode.json')):
                result = episode.render(root)
            self.assertEqual((root / 'plate.mp4').read_bytes(), b'fictional')
            self.assertFalse(result['publishable'])

    def test_headline_requires_short_explicit_text(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fixture(root)
            (root / 'plate.mp4').write_bytes(b'fictional')
            for beat in BEATS:
                file = root / 'audio' / (beat + '.wav')
                file.parent.mkdir(exist_ok=True)
                file.write_bytes(b'fictional')
            (root / 'graphics.json').write_text(json.dumps({'headline': 'x' * 56}))
            with self.assertRaisesRegex(ValueError, '1–55'):
                episode.render(root)


if __name__ == '__main__':
    unittest.main()
