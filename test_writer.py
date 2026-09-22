import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from writer import check_script, request_body, reserve, run


def fixture():
    # Fictional evidence tests plumbing only, never represents medical research.
    return {'id': 'fictional-test', 'revision': 1, 'question': 'Why did the fictional gauge move?',
            'canon': {'voice': 'curious'}, 'hypotheses': [],
            'sources': [{'id': 's1', 'url': 'https://example.org', 'locator': 'fixture',
                         'excerpt': 'Fictional gauge moved.', 'rights_status': 'permitted'}],
            'claims': [{'id': 'c1', 'type': 'fact', 'status': 'verified', 'source_ids': ['s1'],
                        'text': 'Fictional gauge moved.', 'reviewer': 'test', 'limitations': 'Fiction only'}]}


def script():
    return {'title': 'Fictional test', 'open_question': 'What next?', 'segments': [
        {'beat': b, 'text': 'Fictional test sentence.', 'claim_ids': ['c1'], 'production_note': 'Proposed'}
        for b in ['opening', 'explanations', 'evidence', 'limits', 'next_test']]}


class WriterTests(unittest.TestCase):
    def test_dry_run_no_call(self):
        with patch('writer.call_openai') as api:
            result = run(fixture(), 'short', 'gpt-4o-mini', 'unused')
            api.assert_not_called()
            self.assertEqual(result['api_calls'], 0)

    def test_missing_claims(self):
        case = fixture(); case['claims'] = []
        with self.assertRaises(ValueError): request_body(case, 'short', 'x')

    def test_missing_locator(self):
        case = fixture(); del case['sources'][0]['locator']
        with self.assertRaises(ValueError): request_body(case, 'short', 'x')

    def test_unreviewed_rights(self):
        case = fixture(); case['sources'][0]['rights_status'] = 'unknown'
        with self.assertRaises(ValueError): request_body(case, 'short', 'x')

    def test_unknown_citation(self):
        draft = script(); draft['segments'][0]['claim_ids'] = ['invented']
        with self.assertRaises(ValueError): check_script(draft, fixture()['claims'])

    def test_missing_beat(self):
        draft = script(); draft['segments'].pop()
        with self.assertRaises(ValueError): check_script(draft, fixture()['claims'])

    def test_budget_and_duplicate(self):
        with sqlite3.connect(':memory:') as db:
            reserve(db, 'a', .2, .3)
            with self.assertRaises(ValueError): reserve(db, 'a', .01, 1)
            with self.assertRaises(ValueError): reserve(db, 'b', .2, .3)
            with self.assertRaises(ValueError): reserve(db, 'c', .1, float('nan'))

    def test_live_gate(self):
        with patch.dict(os.environ, {'OPENAI_LIVE_ENABLED': 'false'}), patch('writer.call_openai') as api:
            with self.assertRaises(ValueError): run(fixture(), 'short', 'x', 'unused', live=True)
            api.assert_not_called()

    def test_success_is_review_only_and_no_repeat(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
                'OPENAI_LIVE_ENABLED': 'true', 'OPENAI_API_KEY': 'test-only'}), patch(
                'writer.call_openai', return_value=(script(), {'input_tokens': 10}, 'fixture')) as api:
            result = run(fixture(), 'short', 'x', root, True, 1, 1, 1)
            self.assertFalse(result['publishable'])
            self.assertTrue((Path(result['path']) / 'script.md').exists())
            with self.assertRaises(ValueError): run(fixture(), 'short', 'x', root, True, 1, 1, 1)
            self.assertEqual(api.call_count, 1)

    def test_ambiguous_failure_not_retried(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {
                'OPENAI_LIVE_ENABLED': 'true', 'OPENAI_API_KEY': 'test-only'}), patch(
                'writer.call_openai', side_effect=RuntimeError('unknown')) as api:
            with self.assertRaises(RuntimeError): run(fixture(), 'short', 'x', root, True, 1, 1, 1)
            with self.assertRaises(ValueError): run(fixture(), 'short', 'x', root, True, 1, 1, 1)
            self.assertEqual(api.call_count, 1)
