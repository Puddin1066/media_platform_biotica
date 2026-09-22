"""Connect a reviewed OpenAI script to an Instagram Reels production package.

The writer creates a draft. A reviewer pins its exact script hash and supplies
short visual search queries. Footage discovery and assembly follow those cues.
Runway still supplies the host video externally; Meta publishing is downstream.
"""
import argparse
import json
import os
from pathlib import Path

from studio import digest
from writer import check_script
from footage import discover, plan, render
from remotion_handoff import package as package_remotion


def storyboard(draft, review):
    if draft.get('status') != 'review_required':
        raise ValueError('Expected writer draft awaiting review')
    script = check_script(draft['script'], draft['case']['claims'])
    script_hash = digest(script)
    if review.get('status') != 'approved' or review.get('script_sha256') != script_hash \
            or not review.get('reviewer'):
        raise ValueError('Review must name reviewer and pin the exact script')
    queries = review.get('visual_queries', {})
    if not isinstance(queries, dict):
        raise ValueError('visual_queries must map beats to searches')
    cues = []
    for segment in script['segments']:
        beat = segment['beat']
        query = queries.get(beat, segment['production_note'])
        if not isinstance(query, str) or not query.strip():
            raise ValueError('Each beat needs a visual search query')
        cues.append({'cue_id': beat, 'spoken_text': segment['text'],
                     'claim_ids': segment['claim_ids'],
                     'search_query': query.strip()})
    if set(queries) - {cue['cue_id'] for cue in cues}:
        raise ValueError('Unknown beat in visual queries')
    return {'schema_version': 1, 'topic': draft['case']['question'],
            'script_sha256': script_hash, 'reviewer': review['reviewer'],
            'cues': cues, 'status': 'awaiting_footage'}


def plan_from_script(board, catalog, approvals):
    """Every selected shot must map to a reviewed beat and candidate."""
    if board.get('status') != 'awaiting_footage' or \
            catalog.get('script_sha256') != board.get('script_sha256'):
        raise ValueError('Catalog and storyboard must pin the same approved script')
    cues = {cue['cue_id']: cue for cue in board['cues']}
    candidates = {row['id']: row for row in catalog['candidates']}
    if {a.get('cue_id') for a in approvals} != set(cues):
        raise ValueError('Every spoken beat must have a visual shot')
    for shot in approvals:
        if shot['candidate_id'] not in candidates or \
                shot['cue_id'] not in candidates[shot['candidate_id']].get('cue_ids', []):
            raise ValueError('Candidate was not sourced for its assigned beat')
    result = plan(catalog, approvals)
    for shot, approval in zip(result['shots'], approvals):
        shot['cue_id'] = approval['cue_id']
        shot['claim_ids'] = cues[approval['cue_id']]['claim_ids']
    result['script_sha256'] = board['script_sha256']
    result['reviewer'] = board['reviewer']
    result['destination'] = 'Instagram Reels'
    return result


def discover_for_script(board, youtube_key=None, instagram_catalogs=()):
    """Search each beat's visual cue, retaining the script relationship."""
    if board.get('status') != 'awaiting_footage':
        raise ValueError('Approved storyboard required')
    candidates = {}
    for cue in board['cues']:
        for row in discover(cue['search_query'], youtube_key, limit=10)['candidates']:
            if row['id'] not in candidates:
                candidates[row['id']] = {**row, 'cue_ids': []}
            candidates[row['id']]['cue_ids'].append(cue['cue_id'])
    for source in instagram_catalogs:
        cue_id = source['cue_id']
        if cue_id not in {c['cue_id'] for c in board['cues']}:
            raise ValueError('Instagram source uses an unknown script cue')
        for row in source['candidates']:
            if row['id'] not in candidates:
                candidates[row['id']] = {**row, 'cue_ids': []}
            if cue_id not in candidates[row['id']]['cue_ids']:
                candidates[row['id']]['cue_ids'].append(cue_id)
    return {'schema_version': 1, 'topic': board['topic'],
            'script_sha256': board['script_sha256'],
            'candidates': list(candidates.values()),
            'status': 'awaiting_source_selection'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    print(target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    s = sub.add_parser('storyboard')
    s.add_argument('--draft', required=True)
    s.add_argument('--review', required=True)
    s.add_argument('--output', required=True)
    d = sub.add_parser('discover')
    d.add_argument('--storyboard', required=True)
    d.add_argument('--youtube', action='store_true')
    d.add_argument('--instagram-catalog', action='append', default=[],
                   help='Instagram hashtag lead JSON with cue_id, from approved API access')
    d.add_argument('--output', required=True)
    q = sub.add_parser('plan')
    q.add_argument('--storyboard', required=True)
    q.add_argument('--catalog', required=True)
    q.add_argument('--approvals', required=True)
    q.add_argument('--output', required=True)
    r = sub.add_parser('render')
    r.add_argument('--plan', required=True)
    r.add_argument('--host', required=True, help='Runway output file')
    r.add_argument('--output', required=True)
    m = sub.add_parser('package-remotion')
    m.add_argument('--plan', required=True)
    m.add_argument('--plate', required=True, help='Reusable host video plate')
    m.add_argument('--voice', help='Optional episode narration, at least 30 seconds')
    m.add_argument('--plate-start', type=float, default=0)
    m.add_argument('--loop-plate', action='store_true')
    m.add_argument('--output-dir', default='remotion')
    args = p.parse_args()
    if args.command == 'storyboard':
        write(args.output, storyboard(read(args.draft), read(args.review)))
    elif args.command == 'discover':
        key = os.environ.get('YOUTUBE_API_KEY') if args.youtube else None
        if args.youtube and not key:
            p.error('YOUTUBE_API_KEY required for YouTube discovery')
        write(args.output, discover_for_script(
            read(args.storyboard), key, [read(path) for path in args.instagram_catalog]))
    elif args.command == 'plan':
        write(args.output, plan_from_script(read(args.storyboard),
                                             read(args.catalog), read(args.approvals)['approvals']))
    elif args.command == 'package-remotion':
        print(package_remotion(read(args.plan), args.plate, args.output_dir,
                               args.voice, args.plate_start, args.loop_plate))
    else:
        print(render(read(args.plan), args.output, args.host))


if __name__ == '__main__':
    main()
