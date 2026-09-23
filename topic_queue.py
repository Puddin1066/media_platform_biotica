"""Turn researched story leads into blocked, reusable inquiry cases.

This is an editorial intake tool, not a finding of misconduct. It deliberately
exports pending claims and uncleared source notes: the web writer may research
them, but the reviewed-claim writer cannot treat them as verified evidence.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from studio import validate

QUEUE = Path(__file__).parent / 'cases' / 'documented-conduct-topics.json'
CANON = Path(__file__).parent / 'cases' / 'mens-health.json'
STATUSES = {'corporate_guilty_plea', 'affirmed_court_liability',
            'criminal_sentence_and_fda_lab_finding', 'civil_settlement_of_allegations',
            'government_observational_finding_not_conspiracy'}


def load_queue(path=QUEUE):
    """Validate editorial labels and HTTPS receipts before reuse."""
    queue = json.loads(Path(path).read_text(encoding='utf-8'))
    if queue.get('schema_version') != 1 or \
            queue.get('editorial_status') != 'research_candidates_only' or \
            not isinstance(queue.get('topics'), list):
        raise ValueError('Expected an unapproved version-one topic queue')
    ids = set()
    for item in queue['topics']:
        if not isinstance(item.get('id'), str) or item['id'] in ids or \
                item.get('conduct_status') not in STATUSES or \
                not isinstance(item.get('question'), str) or not item['question'] or \
                not isinstance(item.get('angles'), list) or not item['angles']:
            raise ValueError('Invalid or duplicate topic record')
        ids.add(item['id'])
        for source in [item['source'], *item.get('additional_sources', [])]:
            url = urlparse(source.get('url', ''))
            if url.scheme != 'https' or not url.hostname or not source.get('locator'):
                raise ValueError('Sources need an HTTPS URL and document locator')
    return queue


def case_seed(item, canon):
    """Carry a lead into the existing case model without certifying its claims."""
    sources = [item['source'], *item.get('additional_sources', [])]
    case = {'id': item['id'], 'revision': 1, 'question': item['question'],
            'canon': canon, 'sources': [
                {'id': f'S{i}', 'url': source['url'], 'locator': source['locator'],
                 'excerpt': '', 'rights_status': 'review_required',
                 'research_note': source['note']} for i, source in enumerate(sources, 1)],
            'claims': [{'id': 'C1', 'type': 'fact', 'text': item['documented_conduct'],
                        'source_ids': [f'S{i}' for i in range(1, len(sources) + 1)],
                        'status': 'pending', 'reviewer': '',
                        'limitations': item['limitation']}],
            'hypotheses': [
                {'id': f'H{i}', 'statement': angle, 'status': 'untested',
                 'next_test': 'Check the primary record and seek a contrary account'}
                for i, angle in enumerate(item['angles'], 1)],
            'editorial_dossier': {'conduct_status': item['conduct_status'],
                                  'health_context': item['health_context'],
                                  'visual_receipts': item['visual_receipts'],
                                  'limitation': item['limitation'],
                                  'research_status': 'needs_claim_and_media_review'}}
    return validate(case)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('list', 'export'))
    parser.add_argument('--topic-id', help='Queue ID for export')
    parser.add_argument('--output', help='Private or local output JSON for export')
    args = parser.parse_args()
    queue = load_queue()
    if args.command == 'list':
        print(json.dumps([{'id': t['id'], 'question': t['question'],
                           'conduct_status': t['conduct_status']} for t in queue['topics']], indent=2))
        return
    if not args.topic_id or not args.output:
        parser.error('export requires --topic-id and --output')
    item = next((t for t in queue['topics'] if t['id'] == args.topic_id), None)
    if item is None:
        parser.error('Unknown topic ID')
    canon = json.loads(CANON.read_text(encoding='utf-8'))['canon']
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(case_seed(item, canon), indent=2) + '\n', encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
