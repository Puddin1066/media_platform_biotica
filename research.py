"""Bounded Europe PMC searches and an auditable, human-reviewed hypothesis loop."""
import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import urllib.parse
import urllib.request
from studio import digest, validate

ENDPOINT = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search'


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain(value):
    parser = Text()
    parser.feed(value or '')
    return ' '.join(' '.join(parser.parts).split())


def fetch(query, size):
    url = ENDPOINT + '?' + urllib.parse.urlencode({
        'query': query, 'format': 'json', 'resultType': 'core', 'pageSize': size})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(url, timeout=30) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        result = json.loads(raw)
        if not isinstance(result.get('hitCount'), int) or not isinstance(result.get('resultList', {}).get('result'), list):
            raise ValueError('Invalid response')
        return result
    except (OSError, ValueError, TypeError):
        raise RuntimeError('Literature provider failed; no empty result substituted') from None


def collect(case, plan, size=5, search=fetch):
    validate(case)
    hypotheses = {h['id'] for h in case['hypotheses']}
    if not isinstance(plan, list) or not 1 <= len(plan) <= 8 or not 1 <= size <= 25:
        raise ValueError('Use 1–8 searches and 1–25 results per search')
    for entry in plan:
        if entry.get('hypothesis_id') not in hypotheses or not isinstance(entry.get('query'), str) or not 1 <= len(entry['query'].strip()) <= 500:
            raise ValueError('Each query needs a known hypothesis and bounded query text')
    papers, identities, searches = [], {}, []
    for entry in plan:
        result = search(entry['query'], size)
        ids = []
        for item in result['resultList']['result'][:size]:
            source, pid = item.get('source'), item.get('id')
            if not source or not pid:
                raise ValueError('Provider record missing identifier')
            aliases = ['epmc:' + source + ':' + pid]
            if item.get('pmid'):
                aliases.append('pmid:' + item['pmid'])
            if item.get('doi'):
                aliases.append('doi:' + item['doi'].lower().strip())
            existing = {identities[a] for a in aliases if a in identities}
            if len(existing) > 1:
                raise ValueError('Conflicting bibliographic identities require manual reconciliation')
            sid = next(iter(existing), aliases[0])
            if not existing:
                papers.append({'id': sid, 'title': plain(item.get('title')),
                    'authors': item.get('authorString', ''), 'doi': item.get('doi'),
                    'pmid': item.get('pmid'), 'publication_date': item.get('firstPublicationDate'),
                    'url': 'https://europepmc.org/article/' + urllib.parse.quote(source, safe='') + '/' + urllib.parse.quote(pid, safe=''),
                    'abstract': plain(item.get('abstractText')), 'locator': 'abstract',
                    'license_reported': item.get('license'), 'rights_status': 'unreviewed',
                    'publication_types': item.get('pubTypeList', {}).get('pubType', []),
                    'correction_links': item.get('commentCorrectionList', {}).get('commentCorrection', []),
                    'status': 'pending'})
            for alias in aliases:
                identities[alias] = sid
            if sid not in ids:
                ids.append(sid)
        searches.append({**entry, 'hit_count': result['hitCount'], 'source_ids': ids,
                         'scope': 'first relevance-ranked page; not a systematic review'})
    return {'version': 1, 'case_hash': digest(case), 'case': case,
            'retrieved_at': datetime.now(timezone.utc).isoformat(), 'provider': ENDPOINT,
            'page_size': size, 'searches': searches, 'sources': papers,
            'publishable': False, 'status': 'review_required'}


def review_queue(bundle):
    return {'bundle_hash': digest(bundle), 'reviews': [
        {'hypothesis_id': h['id'], 'source_id': sid, 'relation': 'unreviewed',
         'quote': '', 'rationale': '', 'limitations': '', 'reviewer': '',
         'next_test': h.get('next_test', ''), 'next_query': ''}
        for h in bundle['case']['hypotheses']
        for sid in sorted({sid for q in bundle['searches'] if q['hypothesis_id'] == h['id']
                           for sid in q['source_ids']})]}


def advance(bundle, review):
    if review.get('bundle_hash') != digest(bundle):
        raise ValueError('Review does not match this evidence snapshot')
    allowed = {(r['hypothesis_id'], r['source_id']) for r in review_queue(bundle)['reviews']}
    sources = {s['id']: s for s in bundle['sources']}
    seen, findings, queries = set(), [], []
    for row in review['reviews']:
        pair = (row['hypothesis_id'], row['source_id'])
        if pair not in allowed or pair in seen:
            raise ValueError('Unknown or duplicate review link')
        seen.add(pair)
        if row['relation'] == 'unreviewed':
            continue
        if row['relation'] not in ['supports', 'challenges', 'unclear']:
            raise ValueError('Invalid evidence relationship')
        for field in ['quote', 'rationale', 'limitations', 'reviewer', 'next_test']:
            if not isinstance(row.get(field), str) or not row[field].strip():
                raise ValueError('Completed reviews need quotation, reasoning, limits, reviewer and next test')
        if row['quote'] not in sources[row['source_id']]['abstract']:
            raise ValueError('Quotation is not present in the retrieved abstract')
        findings.append({**row, 'status': 'editorial_review_required'})
        query = row.get('next_query', '').strip()
        if query and len(query) <= 500:
            entry = {'hypothesis_id': row['hypothesis_id'], 'query': query}
            if entry not in queries:
                queries.append(entry)
        elif query:
            raise ValueError('Next query too long')
    return {'bundle_hash': digest(bundle), 'findings': findings, 'next_plan': queries,
            'unreviewed_links': len(allowed) - len(findings), 'publishable': False,
            'notice': 'Search matches and quoted text do not establish causality or scientific validity.'}


def save(root, record):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (digest(record) + '.json')
    content = json.dumps(record, indent=2, ensure_ascii=False) + '\n'
    try:
        with path.open('x', encoding='utf-8') as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_text(encoding='utf-8') != content:
            raise ValueError('Existing snapshot was modified')
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    c = sub.add_parser('collect')
    c.add_argument('--case', default='cases/mens-health.json')
    c.add_argument('--plan', default='cases/research-plan.json')
    c.add_argument('--page-size', type=int, default=5)
    r = sub.add_parser('review')
    r.add_argument('--bundle', required=True)
    r.add_argument('--review', required=True)
    for command in [c, r]:
        command.add_argument('--output', default='outputs/research')
    a = p.parse_args()
    def read(path):
        return json.loads(Path(path).read_text(encoding='utf-8'))
    try:
        if a.command == 'collect':
            bundle = collect(read(a.case), read(a.plan), a.page_size)
            print(json.dumps({'bundle': str(save(a.output, bundle)),
                              'review_template': str(save(a.output, review_queue(bundle))),
                              'unique_sources': len(bundle['sources'])}))
        else:
            result = advance(read(a.bundle), read(a.review))
            print(json.dumps({'review_result': str(save(a.output, result)),
                             'next_plan': str(save(a.output, result['next_plan']))}))
    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
        p.exit(1, 'Research failed; check input structure, source availability and review completeness.\n')


if __name__ == '__main__':
    main()
