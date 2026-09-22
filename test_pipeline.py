import json
import tempfile
import unittest
from pathlib import Path

import pipeline


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.case = 'cases/mens-health.json'
        self.plan = 'cases/research-plan.json'

    def test_bootstrap_exposes_theme_and_media(self):
        data = pipeline.bootstrap(self.case)
        self.assertIn('sperm', data['theme'].lower())
        self.assertEqual(len(data['hypotheses']), 4)
        self.assertIn('short', data['writing_formats'])
        self.assertTrue(any(m['id'] == 'narration_speech' for m in data['media_capabilities']))

    def test_full_dry_run_chain(self):
        with tempfile.TemporaryDirectory() as root:
            run = pipeline.start(
                self.case,
                hypothesis_ids=['H1', 'H2'],
                formats=['short', 'podcast'],
                media_targets=['narration_speech', 'short_video'],
                root=root,
                plan_path=self.plan,
            )
            self.assertEqual(run['stages']['theme']['status'], 'done')
            self.assertEqual(run['stages']['research']['status'], 'ready')

            run = pipeline.advance(run, root=root, live=False)
            self.assertEqual(run['artifacts']['research']['api_calls'], 0)
            self.assertEqual(run['stages']['writing']['status'], 'ready')

            run = pipeline.advance(run, root=root, live=False)
            self.assertEqual(run['stages']['writing']['status'], 'done')
            self.assertEqual(run['artifacts']['writing']['short']['evidence_path'],
                             'openai_web_search')

            run = pipeline.advance(run, root=root, live=False)
            self.assertEqual(run['stages']['media']['status'], 'done')
            media = run['artifacts']['media']['short']
            self.assertEqual(media['job_count'], 2)
            self.assertTrue(media['jobs'][0]['endpoint'].startswith('https://api.dev.runwayml.com/'))

            run = pipeline.advance(run, root=root, live=False)
            self.assertEqual(run['stages']['review']['status'], 'review_required')
            self.assertFalse(run['publishable'])
            self.assertTrue((Path(root) / (run['run_id'] + '.json')).exists())

    def test_skip_research_then_write(self):
        with tempfile.TemporaryDirectory() as root:
            run = pipeline.start(self.case, formats=['newsletter'], root=root)
            run = pipeline.skip_stage(run, 'research', root)
            self.assertEqual(run['stages']['research']['status'], 'skipped')
            run = pipeline.run_writing(run, root=root, live=False)
            self.assertEqual(run['stages']['writing']['status'], 'done')

    def test_writing_blocked_before_research(self):
        with tempfile.TemporaryDirectory() as root:
            run = pipeline.start(self.case, root=root)
            with self.assertRaises(ValueError):
                pipeline.run_writing(run, root=root)


class RunwayTests(unittest.TestCase):
    def test_capabilities_catalog(self):
        import runway
        caps = runway.capabilities()
        ids = {c['id'] for c in caps}
        self.assertTrue({'narration_speech', 'short_video', 'avatar_presenter'} <= ids)

    def test_plan_package_requires_script_for_speech(self):
        import runway
        draft = {
            'case': {'question': 'Fixture?'},
            'script': {
                'title': 'Fixture',
                'segments': [{'text': 'Spoken line for media planning.'}],
            },
        }
        package = runway.plan_package(draft, ['narration_speech', 'sound_bed'], 'podcast')
        self.assertEqual(package['job_count'], 2)
        self.assertIn('/text_to_speech', package['jobs'][0]['endpoint'])
        dry = runway.submit(package['jobs'][0], 'unused', live=False)
        self.assertEqual(dry['api_calls'], 0)

    def test_live_gate(self):
        import os
        import runway
        from unittest.mock import patch
        draft = {'script': {'title': 'x', 'segments': [{'text': 'y'}]}}
        plan = runway.build_request('narration_speech', draft)
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            runway.submit(plan, 'unused', live=True, budget=1, max_usd_per_job=0.1)


if __name__ == '__main__':
    unittest.main()
