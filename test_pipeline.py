"""Script-to-Reels handoff tests using only fictional claims and local files."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline
import instagram
import experiment
import remotion_handoff
from studio import digest


def fictional_draft():
    case = {'question': 'Can a fictional device detect X?',
            'claims': [{'id': 'c1'}]}
    script = {'title': 'Fictional', 'open_question': 'What comes next?',
              'segments': [{'beat': beat, 'text': 'A fictional sentence.',
                            'claim_ids': ['c1'], 'production_note': 'fictional device demo'}
                           for beat in ('opening', 'explanations', 'evidence', 'limits', 'next_test')]}
    return {'status': 'review_required', 'case': case, 'script': script}


class PipelineTests(unittest.TestCase):
    def approved_board(self):
        draft = fictional_draft()
        review = {'status': 'approved', 'reviewer': 'Owner',
                  'script_sha256': digest(draft['script']),
                  'visual_queries': {'evidence': 'fictional assay demonstration'}}
        board = pipeline.storyboard(draft, review)
        return draft, review, board

    def test_script_approval_pins_hash_and_cues(self):
        draft, review, board = self.approved_board()
        self.assertEqual(board['cues'][2]['search_query'], 'fictional assay demonstration')
        with self.assertRaises(ValueError):
            pipeline.storyboard(draft, {**review, 'script_sha256': 'stale'})

    def test_every_shot_maps_to_script_claims(self):
        _, _, board = self.approved_board()
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / 'creator.mp4'
            source.touch()
            beats = [c['cue_id'] for c in board['cues']]
            catalog = {'topic': board['topic'], 'script_sha256': board['script_sha256'],
                       'candidates': [{'id': 'instagram:demo', 'cue_ids': beats}]}
            approvals = [{'candidate_id': 'instagram:demo', 'cue_id': beat,
                          'rights_status': 'approved', 'license_basis': 'creator license',
                          'credit': 'Fictional creator', 'media_source': str(source),
                          'start_seconds': i} for i, beat in enumerate([*beats, beats[-1]])]
            plan = pipeline.plan_from_script(board, catalog, approvals)
            self.assertEqual(plan['destination'], 'Instagram Reels')
            self.assertEqual(plan['shots'][2]['claim_ids'], ['c1'])
            with self.assertRaises(ValueError):
                pipeline.plan_from_script(board, catalog, approvals[:5] + [
                    {**approvals[5], 'cue_id': 'missing'}])

    def test_remotion_handoff_keeps_plate_and_shots_independent(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            plate = root / 'plate.mp4'
            source = root / 'source.mp4'
            plate.write_bytes(b'fictional plate')
            source.write_bytes(b'fictional clip')
            plan = {'status': 'renderable_not_publish_approved', 'target_seconds': 30,
                    'shots': [{'destination_seconds': i * 5, 'duration_seconds': 5,
                               'start_seconds': i * 5, 'media_source': str(source),
                               'license_basis': 'fictional permission', 'credit': 'Fixture',
                               'cue_id': 'opening', 'claim_ids': ['c1']}
                              for i in range(6)]}
            with patch.object(remotion_handoff, 'duration', return_value=10), \
                    patch.object(remotion_handoff, 'run_ffmpeg') as ffmpeg:
                with self.assertRaisesRegex(ValueError, 'Plate is too short'):
                    remotion_handoff.package(plan, plate, root / 'remotion')
                path = remotion_handoff.package(plan, plate, root / 'remotion', loop_plate=True)
            result = json.loads(path.read_text())
            self.assertTrue(result['loop_plate'])
            self.assertEqual(len(result['shots']), 6)
            self.assertEqual(result['shots'][-1]['from'], 750)
            self.assertEqual(result['shots'][0]['claim_ids'], ['c1'])
            self.assertEqual(ffmpeg.call_count, 6)


class InstagramTests(unittest.TestCase):
    def test_top_hashtag_result_is_lead_only(self):
        with patch.object(instagram, 'graph', side_effect=[
                {'data': [{'id': 'tag123'}]},
                {'data': [{'id': 'post123', 'media_type': 'VIDEO',
                           'permalink': 'https://www.instagram.com/reel/123'}]}]):
            row = instagram.discover_hashtag('device', 'owner', 'token')['candidates'][0]
        self.assertIsNone(row['direct_url'])
        self.assertEqual(row['rights_status'], 'creator_permission_needed')

    def test_release_hash_and_no_duplicate_submission(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            movie = root / 'approved.mp4'
            movie.write_bytes(b'fictional rendered movie')
            release = {'status': 'approved_for_publication', 'reviewer': 'Owner',
                       'file': str(movie), 'file_sha256': hashlib.sha256(movie.read_bytes()).hexdigest(),
                       'public_video_url': 'https://media.example.org/approved.mp4',
                       'caption': 'Fictional episode', 'script_sha256': 's1',
                       'footage_plan_sha256': 'p1'}
            ledger = root / 'ledger.sqlite'
            with patch.object(instagram, 'graph', return_value={'id': 'container123'}) as provider:
                result = instagram.create_container(release, ledger, 'owner', 'token')
                self.assertEqual(result['state'], 'container_created')
                with self.assertRaises(ValueError):
                    instagram.create_container(release, ledger, 'owner', 'token')
                self.assertEqual(provider.call_count, 1)
            with patch.object(instagram, 'graph', side_effect=[
                    {'status_code': 'FINISHED'}, {'id': 'media456'},
                    {'data': [{'name': 'views', 'total_value': {'value': 200}}]}]):
                published = instagram.publish_container(result['job'], ledger, 'owner', 'token')
                self.assertEqual(published['media_id'], 'media456')
                snap = instagram.insights(result['job'], ledger, 'token')
                self.assertEqual(snap['metrics'][0]['total_value']['value'], 200)
            movie.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                instagram.validate_release(release)

    def test_same_age_reel_comparison_uses_real_denominators(self):
        snapshots = [{'variant': name, 'published_at': '2026-09-20T00:00:00+00:00',
                      'snapshot': {'media_id': name, 'retrieved_at': '2026-09-22T00:00:00+00:00',
                                   'metrics': [{'name': 'views', 'total_value': {'value': views}},
                                               {'name': 'shares', 'values': [{'value': shares}]}]}}
                     for name, views, shares in [('A', 1000, 12), ('B', 2000, 40)]]
        result = experiment.compare(snapshots)
        self.assertEqual(result['variants'][1]['shares_per_1000_views'], 20.0)
        self.assertEqual(result['status'], 'descriptive_comparison')


if __name__ == '__main__':
    unittest.main()
