"""Bridge a web-search script into the reviewed Satoshi production storyboard.

The model's URLs are discovery evidence, not approved factual claims. An editor
supplies a separately checked case and explicitly maps every spoken beat to its
supporting claim IDs. Both input hashes are locked before the existing footage,
Runway and Remotion stages may use the storyboard.
"""
import argparse
import json
from pathlib import Path

import pipeline
import produce
from speech_timing import BEATS
from studio import digest, validate
from writer import evidence_packet


def source_urls(draft):
    if draft.get('status') != 'review_required' or \
            draft.get('evidence_path') != 'openai_web_search' or \
            draft.get('format') != 'short':
        raise ValueError('A review-required web-search short is required')
    urls = {s['url'] for s in draft.get('sources', []) if s.get('role') == 'cited'}
    produce.check_script(draft['script'], urls)
    return urls


def review_template(draft, case):
    """Give the editor exact hashes and citations without approving anything."""
    source_urls(draft)
    validate(case)
    if case['question'] != draft['case']['question']:
        raise ValueError('Reviewed case must address the drafted question')
    return {'status': 'pending', 'reviewer': '',
            'draft_script_sha256': digest(draft['script']),
            'reviewed_case_sha256': digest(case),
            'claim_ids_by_beat': {segment['beat']: [] for segment in draft['script']['segments']},
            'visual_queries': {},
            'cited_urls_by_beat': {s['beat']: s['source_urls'] for s in draft['script']['segments']},
            'note': 'Verify every factual statement and the source excerpts. Enter checked claim IDs, then set status approved and name the reviewer.'}


def approve(draft, case, review):
    """Enforce explicit claim/source overlap, then reuse the existing storyboard.

    This is a provenance check, not a claim-entailment or medical accuracy check.
    The reviewer attests to those judgments when approving the locked hashes.
    """
    source_urls(draft)
    packet = evidence_packet(case)
    expected = review_template(draft, case)
    if review.get('status') != 'approved' or not str(review.get('reviewer', '')).strip() \
            or review.get('draft_script_sha256') != expected['draft_script_sha256'] \
            or review.get('reviewed_case_sha256') != expected['reviewed_case_sha256']:
        raise ValueError('Named approval must pin the exact web draft and reviewed case')
    mapping = review.get('claim_ids_by_beat')
    if not isinstance(mapping, dict) or set(mapping) != set(BEATS):
        raise ValueError('Map all five beats to checked claim IDs')
    claims = {claim['id']: claim for claim in packet['claims']}
    sources = {source['id']: source for source in packet['sources']}
    segments = []
    for segment in draft['script']['segments']:
        beat = segment['beat']
        ids = mapping[beat]
        if not isinstance(ids, list) or not ids or \
                len(ids) != len(set(ids)) or any(cid not in claims for cid in ids):
            raise ValueError('Every beat requires distinct verified claim IDs')
        supported = {sources[sid]['url'] for cid in ids
                     for sid in claims[cid]['source_ids']}
        if not set(segment['source_urls']) <= supported:
            raise ValueError('Every cited URL in a beat must map to a selected reviewed claim')
        segments.append({k: segment[k] for k in ('beat', 'text', 'production_note')} |
                        {'claim_ids': ids})
    script = {'title': draft['script']['title'], 'segments': segments,
              'open_question': draft['script']['open_question']}
    derived = {'status': 'review_required', 'case': case, 'script': script}
    queries = review.get('visual_queries', {})
    board = pipeline.storyboard(derived, {'status': 'approved',
                                           'reviewer': review['reviewer'],
                                           'script_sha256': digest(script),
                                           'visual_queries': queries})
    board['web_draft_sha256'] = expected['draft_script_sha256']
    board['reviewed_case_sha256'] = expected['reviewed_case_sha256']
    for cue, segment in zip(board['cues'], draft['script']['segments']):
        cue['source_urls'] = segment['source_urls']
    return board


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('template', 'approve'))
    p.add_argument('--draft', required=True)
    p.add_argument('--case', required=True, help='Separately reviewed case JSON')
    p.add_argument('--review', help='Completed review JSON for approve')
    p.add_argument('--output', required=True)
    args = p.parse_args()
    if args.command == 'approve' and not args.review:
        p.error('--review required for approve')
    draft = json.loads(Path(args.draft).read_text(encoding='utf-8'))
    case = json.loads(Path(args.case).read_text(encoding='utf-8'))
    result = review_template(draft, case) if args.command == 'template' else approve(
        draft, case, json.loads(Path(args.review).read_text(encoding='utf-8')))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
