import os
import tempfile
import unittest
from unittest.mock import patch
import analyst
import test_research


class AnalystTests(unittest.TestCase):
    def setUp(self):
        fixture = test_research.ResearchTests()
        fixture.setUp()
        self.bundle = fixture.bundle()
        self.result = fixture.completed(self.bundle)
        for source in self.bundle['sources']:
            source['rights_status'] = 'permitted'

    def test_rights_gate_and_dry_run(self):
        with patch('analyst.call_openai') as call:
            self.assertEqual(analyst.run(self.bundle, 'test', 'unused')['api_calls'], 0)
            call.assert_not_called()
        self.bundle['sources'][0]['rights_status'] = 'unreviewed'
        with self.assertRaises(ValueError):
            analyst.request_body(self.bundle, 'test')

    def test_live_gate(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            analyst.run(self.bundle, 'test', 'unused', live=True)

    def test_live_mock_and_duplicate(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}), patch('analyst.call_openai', return_value=(self.result, {}, 'fixture')) as call:
            result = analyst.run(self.bundle, 'test', d, True, 1, 1, 1)
            self.assertFalse(result['publishable'])
            with self.assertRaises(ValueError):
                analyst.run(self.bundle, 'test', d, True, 1, 1, 1)
            self.assertEqual(call.call_count, 1)

    def test_invented_quote_is_not_saved_as_review(self):
        self.result['reviews'][0]['quote'] = 'fabricated'
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture', 'OPENAI_LIVE_ENABLED': 'true'}), patch('analyst.call_openai', return_value=(self.result, {}, 'fixture')) as call:
            with self.assertRaises(ValueError):
                analyst.run(self.bundle, 'test', d, True, 1, 1, 1)
            with self.assertRaises(ValueError):
                analyst.run(self.bundle, 'test', d, True, 1, 1, 1)
            self.assertEqual(call.call_count, 1)
