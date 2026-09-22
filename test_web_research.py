import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import web_research


class WebResearchTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path('cases/mens-health.json').read_text())
        self.plan = [{'hypothesis_id': 'H1', 'query': 'fixture question'}]
        self.response = {'id': 'fixture', 'status': 'completed', 'usage': {}, 'output': [
            {'type': 'web_search_call', 'action': {'sources': [
                {'url': 'https://example.org/paper', 'title': 'Fixture paper'},
                {'url': 'https://example.org/other', 'title': 'Other'}]}},
            {'type': 'message', 'content': [{'type': 'output_text',
                'text': '# Question\nFixture memo', 'annotations': [
                    {'type': 'url_citation', 'url': 'https://example.org/paper',
                     'title': 'Fixture paper', 'start_index': 0, 'end_index': 7}]}]}]}

    def test_dry_run_makes_no_call(self):
        call = Mock()
        result = web_research.run(self.case, self.plan, 'fixture-model', 'unused', request=call)
        self.assertEqual(result['api_calls'], 0)
        self.assertEqual(result['planned_searches'], 1)
        call.assert_not_called()

    def test_request_is_bounded_and_stateless(self):
        body = web_research.request_body(self.case, self.case['hypotheses'][0], 'query', 'model', 3)
        self.assertFalse(body['store'])
        self.assertEqual(body['tools'], [{'type': 'web_search'}])
        self.assertEqual(body['max_tool_calls'], 3)
        self.assertIn('web_search_call.action.sources', body['include'])

    def test_parse_captures_consulted_and_cited(self):
        memo, sources = web_research.parse_response(self.response)
        self.assertIn('Fixture memo', memo)
        self.assertEqual(len(sources), 2)
        self.assertEqual([s['role'] for s in sources if s['url'].endswith('/paper')], ['cited'])

    def test_parse_rejects_no_citations(self):
        self.response['output'][1]['content'][0]['annotations'] = []
        with self.assertRaises(ValueError):
            web_research.parse_response(self.response)

    def test_live_gate(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            web_research.run(self.case, self.plan, 'model', 'unused', live=True,
                             budget=1, max_usd_per_search=.1)

    def test_mock_live_saves_review_only_bundle_and_deduplicates(self):
        call = Mock(return_value=self.response)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}):
            result = web_research.run(self.case, self.plan, 'model', directory,
                                      True, 1, .1, request=call)
            saved = json.loads(Path(result['bundle']).read_text())
            self.assertFalse(saved['publishable'])
            self.assertEqual(saved['records'][0]['status'], 'human_review_required')
            self.assertEqual(result['unique_sources'], 2)
            with self.assertRaises(ValueError):
                web_research.run(self.case, self.plan, 'model', directory,
                                 True, 1, .1, request=call)
            self.assertEqual(call.call_count, 1)

    def test_failure_keeps_reservation_and_is_not_retried(self):
        call = Mock(side_effect=RuntimeError('fixture'))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}):
            with self.assertRaises(RuntimeError):
                web_research.run(self.case, self.plan, 'model', directory,
                                 True, 1, .1, request=call)
            with self.assertRaises(ValueError):
                web_research.run(self.case, self.plan, 'model', directory,
                                 True, 1, .1, request=call)
            self.assertEqual(call.call_count, 1)

    def test_plan_and_tool_call_limits(self):
        with self.assertRaises(ValueError):
            web_research.run(self.case, [], 'model', 'unused')
        with self.assertRaises(ValueError):
            web_research.request_body(self.case, self.case['hypotheses'][0], 'q', 'm', 9)


if __name__ == '__main__':
    unittest.main()
