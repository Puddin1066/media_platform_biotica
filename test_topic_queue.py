"""The topic intake must remain blocked until factual and media review."""
import json
import tempfile
import unittest
from pathlib import Path

import topic_queue
from writer import evidence_packet


class TopicQueueTests(unittest.TestCase):
    def test_every_researched_topic_exports_without_approved_claims(self):
        queue = topic_queue.load_queue()
        canon = json.loads(topic_queue.CANON.read_text())['canon']
        self.assertEqual(len(queue['topics']), 5)
        for item in queue['topics']:
            case = topic_queue.case_seed(item, canon)
            self.assertEqual(case['editorial_dossier']['conduct_status'],
                             item['conduct_status'])
            self.assertEqual(case['claims'][0]['status'], 'pending')
            self.assertEqual(case['sources'][0]['rights_status'], 'review_required')
            with self.assertRaisesRegex(ValueError, 'No reviewed claims'):
                evidence_packet(case)

    def test_rejects_duplicate_topics_and_insecure_receipts(self):
        queue = topic_queue.load_queue()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'topics.json'
            queue['topics'][1]['id'] = queue['topics'][0]['id']
            path.write_text(json.dumps(queue))
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                topic_queue.load_queue(path)
            queue['topics'][1]['id'] = 'unique'
            queue['topics'][1]['source']['url'] = 'http://example.com/record'
            path.write_text(json.dumps(queue))
            with self.assertRaisesRegex(ValueError, 'HTTPS'):
                topic_queue.load_queue(path)


if __name__ == '__main__':
    unittest.main()
