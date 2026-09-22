import tempfile
import unittest

import costs
import pipeline


class CostTests(unittest.TestCase):
    def test_research_estimate_positive(self):
        est = costs.estimate_research([{'hypothesis_id': 'H1'}, {'hypothesis_id': 'H2'}], 4)
        self.assertGreater(est['usd'], 0)
        self.assertEqual(est['searches'], 2)
        self.assertEqual(est['tool_calls'], 8)

    def test_writing_and_media_estimates(self):
        plan = [{'hypothesis_id': 'H1'}]
        writing = costs.estimate_writing(['short', 'podcast'], plan, 6)
        media = costs.estimate_media(['short'], ['narration_speech', 'short_video'])
        self.assertGreater(writing['usd'], 0)
        self.assertEqual(media['job_count'], 2)
        self.assertGreater(media['usd'], 0)

    def test_actual_from_usage(self):
        actual = costs.actual_from_openai_usage(
            {'input_tokens': 1000, 'output_tokens': 500}, tool_calls=2)
        self.assertIsNotNone(actual['usd'])
        self.assertEqual(actual['input_tokens'], 1000)

    def test_pipeline_records_costs_on_dry_run(self):
        with tempfile.TemporaryDirectory() as root:
            run = pipeline.start(
                formats=['short'],
                media_targets=['narration_speech'],
                root=root,
                hypothesis_ids=['H1'],
            )
            self.assertGreater(run['planned_cost']['estimate_usd_total'], 0)
            run = pipeline.advance(run, root=root, live=False)
            cost = run['stages']['research']['cost']
            self.assertGreater(cost['estimate']['usd'], 0)
            self.assertEqual(cost['actual']['usd'], 0.0)
            self.assertEqual(cost['actual']['source'], 'dry_run_zero')
            self.assertIn('estimate_usd_total', run['cost_rollup'])


if __name__ == '__main__':
    unittest.main()
