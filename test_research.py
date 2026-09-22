import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import research


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads(Path('cases/mens-health.json').read_text())
        self.plan = [{'hypothesis_id': 'H1', 'query': 'first'},
                     {'hypothesis_id': 'H2', 'query': 'second'}]
        self.result = {'hitCount': 1, 'resultList': {'result': [
            {'source': 'MED', 'id': '1', 'pmid': '1', 'doi': '10.example/X',
             'title': 'Fixture only', 'abstractText': '<p>A fictional measurement varied.</p>'}]}}

    def bundle(self):
        return research.collect(self.case, self.plan, search=lambda *_: self.result)

    def test_deduplicates_preserving_hypothesis_links(self):
        b = self.bundle()
        self.assertEqual(len(b['sources']), 1)
        self.assertEqual(len(research.review_queue(b)['reviews']), 2)
        self.assertEqual(b['sources'][0]['rights_status'], 'unreviewed')
        self.assertFalse(b['publishable'])
        self.assertEqual(self.case['claims'], [])

    def test_doi_alias(self):
        other = copy.deepcopy(self.result)
        other['resultList']['result'][0].update(source='PMC', id='PMC1', pmid='')
        results = iter([self.result, other])
        self.assertEqual(len(research.collect(self.case, self.plan, search=lambda *_: next(results))['sources']), 1)

    def test_missing_abstract_and_zero_results(self):
        self.result['resultList']['result'][0].pop('abstractText')
        self.assertEqual(self.bundle()['sources'][0]['abstract'], '')
        self.result = {'hitCount': 0, 'resultList': {'result': []}}
        self.assertEqual(self.bundle()['sources'], [])

    def test_validation_precedes_network(self):
        for plan, size in [([], 5), (self.plan, 26), ([{'hypothesis_id': 'H99', 'query': 'a'}], 5)]:
            with self.assertRaises(ValueError):
                research.collect(self.case, plan, size, search=lambda *_: self.fail('network'))

    def test_failure_not_empty_results(self):
        with patch('urllib.request.build_opener') as opener:
            opener.return_value.open.side_effect = OSError('private detail')
            with self.assertRaisesRegex(RuntimeError, '^Literature provider failed'):
                research.fetch('query', 1)

    def completed(self, b):
        q = research.review_queue(b)
        q['reviews'][0].update(relation='unclear', quote='measurement varied',
            rationale='Fixture assessment', limitations='Abstract only', reviewer='Test reviewer',
            next_query='measurement replication')
        return q

    def test_iteration_does_not_approve_claims(self):
        b = self.bundle()
        result = research.advance(b, self.completed(b))
        self.assertEqual(result['unreviewed_links'], 1)
        self.assertEqual(result['next_plan'][0]['query'], 'measurement replication')
        self.assertFalse(result['publishable'])
        self.assertEqual(result['findings'][0]['status'], 'editorial_review_required')

    def test_bad_quote_citation_snapshot_and_duplicate_rejected(self):
        b = self.bundle()
        for field, value in [('quote', 'invented'), ('source_id', 'missing'), ('reviewer', '')]:
            q = self.completed(b)
            q['reviews'][0][field] = value
            with self.assertRaises(ValueError):
                research.advance(b, q)
        q = self.completed(b)
        q['reviews'].append(q['reviews'][0])
        with self.assertRaises(ValueError):
            research.advance(b, q)
        q = self.completed(b)
        q['bundle_hash'] = 'stale'
        with self.assertRaises(ValueError):
            research.advance(b, q)

    def test_immutable_snapshots(self):
        with tempfile.TemporaryDirectory() as d:
            path = research.save(d, {'a': 1})
            self.assertEqual(path, research.save(d, {'a': 1}))
            path.write_text('changed')
            with self.assertRaises(ValueError):
                research.save(d, {'a': 1})


if __name__ == '__main__':
    unittest.main()
