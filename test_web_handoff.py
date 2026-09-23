"""Fictional URL-to-reviewed-claim handoff; no provider calls."""
import copy
import unittest

import produce
import web_handoff


URL = 'https://example.test/fictional-report'


def fixtures():
    case = {'id': 'fictional', 'revision': 1, 'question': 'What does X measure?',
            'canon': 'Fictional fixture', 'hypotheses': [{'id': 'H1', 'statement': 'A'}],
            'sources': [{'id': 's1', 'url': URL, 'locator': 'p. 1',
                         'excerpt': 'Fictional test observation', 'rights_status': 'permitted'}],
            'claims': [{'id': 'c1', 'text': 'Fictional observation', 'reviewer': 'Editor',
                        'limitations': 'Fictional sample', 'status': 'verified',
                        'type': 'fact', 'source_ids': ['s1']}]}
    script = {'title': 'X', 'open_question': 'What remains?',
              'segments': [{'beat': b, 'text': 'Fictional words.',
                            'source_urls': [URL], 'production_note': 'Show fictional figure'}
                           for b in produce.BEATS]}
    draft = {'status': 'review_required', 'format': 'short',
             'evidence_path': 'openai_web_search', 'case': case, 'script': script,
             'sources': [{'url': URL, 'role': 'cited'}]}
    return draft, case


class WebHandoffTests(unittest.TestCase):
    def test_only_explicit_verified_mapping_creates_storyboard(self):
        draft, case = fixtures()
        review = web_handoff.review_template(draft, case)
        self.assertEqual(review['status'], 'pending')
        with self.assertRaisesRegex(ValueError, 'Named approval'):
            web_handoff.approve(draft, case, review)
        review.update(status='approved', reviewer='Editor')
        review['claim_ids_by_beat'] = {b: ['c1'] for b in produce.BEATS}
        board = web_handoff.approve(draft, case, review)
        self.assertEqual(board['status'], 'awaiting_footage')
        self.assertEqual(board['cues'][0]['source_urls'], [URL])
        self.assertEqual(board['cues'][0]['claim_ids'], ['c1'])
        self.assertEqual([c['cue_id'] for c in board['cues']], list(produce.BEATS))

    def test_stale_script_case_and_unrelated_claim_fail_closed(self):
        draft, case = fixtures()
        review = web_handoff.review_template(draft, case)
        review.update(status='approved', reviewer='Editor')
        review['claim_ids_by_beat'] = {b: ['c1'] for b in produce.BEATS}
        changed = copy.deepcopy(draft)
        changed['script']['segments'][0]['text'] = 'Changed narration.'
        with self.assertRaisesRegex(ValueError, 'exact web draft'):
            web_handoff.approve(changed, case, review)
        altered_case = copy.deepcopy(case)
        altered_case['sources'][0]['url'] = 'https://example.test/other'
        review['reviewed_case_sha256'] = web_handoff.review_template(draft, altered_case)['reviewed_case_sha256']
        with self.assertRaisesRegex(ValueError, 'cited URL'):
            web_handoff.approve(draft, altered_case, review)
        review['reviewed_case_sha256'] = web_handoff.review_template(draft, case)['reviewed_case_sha256']
        review['claim_ids_by_beat']['limits'] = ['absent']
        with self.assertRaisesRegex(ValueError, 'verified claim'):
            web_handoff.approve(draft, case, review)

    def test_unsafe_or_unsupported_draft_is_rejected(self):
        draft, case = fixtures()
        draft['script']['segments'][0]['source_urls'] = ['https://example.test/uncited']
        with self.assertRaisesRegex(ValueError, 'not web-search cited'):
            web_handoff.review_template(draft, case)
        draft, case = fixtures()
        case['claims'][0]['status'] = 'pending'
        review = web_handoff.review_template(draft, case)
        review.update(status='approved', reviewer='Editor')
        review['claim_ids_by_beat'] = {b: ['c1'] for b in produce.BEATS}
        with self.assertRaisesRegex(ValueError, 'No reviewed claims'):
            web_handoff.approve(draft, case, review)


if __name__ == '__main__':
    unittest.main()
