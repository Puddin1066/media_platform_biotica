import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import produce


class ProduceTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path('cases/mens-health.json').read_text())
        self.plan = [{'hypothesis_id': 'H1', 'query': 'fixture web question'}]
        self.script = {
            'title': 'Fixture web draft',
            'open_question': 'What still needs a discriminating test?',
            'segments': [
                {
                    'beat': beat,
                    'text': 'Fixture sentence grounded by search.',
                    'source_urls': ['https://example.org/paper'],
                    'production_note': 'Proposed visual only',
                }
                for beat in produce.BEATS
            ],
        }
        self.response = {
            'id': 'fixture',
            'status': 'completed',
            'usage': {},
            'output': [
                {
                    'type': 'web_search_call',
                    'action': {
                        'sources': [
                            {'url': 'https://example.org/paper', 'title': 'Fixture paper'},
                            {'url': 'https://example.org/other', 'title': 'Other'},
                        ]
                    },
                },
                {
                    'type': 'message',
                    'content': [{
                        'type': 'output_text',
                        'text': json.dumps(self.script),
                        'annotations': [{
                            'type': 'url_citation',
                            'url': 'https://example.org/paper',
                            'title': 'Fixture paper',
                            'start_index': 0,
                            'end_index': 7,
                        }],
                    }],
                },
            ],
        }

    def test_dry_run_makes_no_call(self):
        call = Mock()
        result = produce.run(self.case, self.plan, 'short', 'model', 'unused', request=call)
        self.assertEqual(result['api_calls'], 0)
        self.assertEqual(result['evidence_path'], 'openai_web_search')
        self.assertEqual(result['search_cues'], 1)
        call.assert_not_called()

    def test_request_requires_web_search_tool(self):
        body = produce.request_body(self.case, self.plan, 'short', 'model', 4)
        self.assertEqual(body['tools'], [{'type': 'web_search'}])
        self.assertFalse(body['store'])
        self.assertEqual(body['max_tool_calls'], 4)
        self.assertIn('web_search_call.action.sources', body['include'])
        self.assertEqual(body['text']['format']['type'], 'json_schema')

    def test_default_plan_from_hypotheses(self):
        plan = produce.default_plan(self.case)
        self.assertEqual(len(plan), 4)
        self.assertTrue(all(entry['hypothesis_id'].startswith('H') for entry in plan))

    def test_seed_case_supports_web_produce_dry_run(self):
        """Unlike writer.py, produce does not require pre-reviewed claims."""
        plan = produce.default_plan(self.case)
        result = produce.run(self.case, plan, 'podcast', 'model', 'unused')
        self.assertEqual(result['mode'], 'dry_run')
        self.assertEqual(result['search_cues'], 4)

    def test_parse_and_check_require_cited_urls(self):
        script, sources = produce.parse_response(self.response)
        cited = [s['url'] for s in sources if s['role'] == 'cited']
        produce.check_script(script, cited)
        bad = json.loads(json.dumps(self.script))
        bad['segments'][0]['source_urls'] = ['https://example.org/invented']
        with self.assertRaises(ValueError):
            produce.check_script(bad, cited)

    def test_parse_rejects_draft_without_web_citations(self):
        self.response['output'][1]['content'][0]['annotations'] = []
        with self.assertRaises(ValueError):
            produce.parse_response(self.response)

    def test_live_gate(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            produce.run(self.case, self.plan, 'short', 'model', 'unused', live=True,
                        budget=1, max_usd_per_run=.2)

    def test_mock_live_saves_review_only_web_backed_draft(self):
        call = Mock(return_value=self.response)
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}):
            result = produce.run(self.case, self.plan, 'short', 'model', directory,
                                 True, 1, .25, request=call)
            self.assertFalse(result['publishable'])
            draft = json.loads((Path(result['path']) / 'draft.json').read_text())
            self.assertEqual(draft['evidence_path'], 'openai_web_search')
            self.assertEqual(draft['status'], 'review_required')
            self.assertTrue((Path(result['path']) / 'script.md').exists())
            with self.assertRaises(ValueError):
                produce.run(self.case, self.plan, 'short', 'model', directory,
                            True, 1, .25, request=call)
            self.assertEqual(call.call_count, 1)

    def test_ambiguous_failure_not_retried(self):
        call = Mock(side_effect=RuntimeError('fixture'))
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {
                'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}):
            with self.assertRaises(RuntimeError):
                produce.run(self.case, self.plan, 'short', 'model', directory,
                            True, 1, .25, request=call)
            with self.assertRaises(ValueError):
                produce.run(self.case, self.plan, 'short', 'model', directory,
                            True, 1, .25, request=call)
            self.assertEqual(call.call_count, 1)

    def test_tool_call_limits(self):
        with self.assertRaises(ValueError):
            produce.request_body(self.case, self.plan, 'short', 'model', 9)
        with self.assertRaises(ValueError):
            produce.run(self.case, [], 'short', 'model', 'unused')


if __name__ == '__main__':
    unittest.main()
