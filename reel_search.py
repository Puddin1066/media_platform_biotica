"""Systematic Instagram Reel lead search for a screen-record → splice workflow.

Flow:
  topic / cue text → hashtags → Graph hashtag VIDEO leads (as @byoticallc) →
  ranked recording queue → local screen recordings → duration gate (<10s) →
  footage approvals for pipeline splice.

This module never scrapes Instagram in a browser, never downloads Reel bytes,
and never treats a permalink as a render source. View counts for other creators'
hashtag media are not returned by Meta's hashtag edges; likes/comments are the
available ranking proxies until a local recording is reviewed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import instagram

DEFAULT_ACCOUNT = 'byoticallc'
DEFAULT_MAX_SOURCE_SECONDS = 10
STOPWORDS = {
    'a', 'an', 'and', 'for', 'from', 'in', 'of', 'on', 'or', 'the', 'to', 'with',
}


def hashtags_for_topic(topic, extra_tags=()):
    """Derive searchable hashtags from a medical/editorial topic string."""
    text = (topic or '').strip().lower()
    if not text:
        raise ValueError('Topic is required')
    compact = re.sub(r'[^a-z0-9]+', '', text)
    words = [w for w in re.findall(r'[a-z0-9]+', text) if w not in STOPWORDS]
    tags = []
    if compact:
        tags.append(compact)
    if len(words) >= 2:
        tags.append(''.join(words))
        tags.append(words[0] + words[-1])
    tags.extend(words)
    for tag in extra_tags:
        cleaned = re.sub(r'[^a-z0-9]+', '', tag.lower().lstrip('#'))
        if cleaned:
            tags.append(cleaned)
    # Preserve order, drop empties/duplicates, keep Graph's one-token hashtag shape.
    ordered = []
    seen = set()
    for tag in tags:
        if tag and tag not in seen and ' ' not in tag:
            seen.add(tag)
            ordered.append(tag)
    if not ordered:
        raise ValueError('Could not derive hashtags from topic')
    return ordered


def search_reels(topic, ig_user_id, token, cue_id='evidence', tags=None,
                 edge='top_media', version='v25.0', limit=24,
                 account=DEFAULT_ACCOUNT):
    """Search Reels/VIDEO hashtag leads and build a ranked screen-record queue."""
    tag_list = list(tags) if tags else hashtags_for_topic(topic)
    by_id = {}
    searched = []
    for tag in tag_list:
        result = instagram.discover_hashtag(tag, ig_user_id, token, version, edge=edge)
        searched.append({'tag': tag, 'count': len(result['candidates'])})
        for row in result['candidates']:
            existing = by_id.get(row['id'])
            if existing is None or row['engagement']['rank_score'] > existing['engagement']['rank_score']:
                item = dict(row)
                item['cue_id'] = cue_id
                by_id[row['id']] = item
    ranked = sorted(by_id.values(),
                    key=lambda row: row['engagement']['rank_score'], reverse=True)
    ranked = ranked[: max(1, int(limit))]
    queue = []
    for index, row in enumerate(ranked, start=1):
        stem = row['id'].replace(':', '_')
        queue.append({
            'rank': index,
            'candidate_id': row['id'],
            'cue_id': cue_id,
            'permalink': row['page_url'],
            'title': row['title'],
            'tag': row['tag'],
            'like_count': row['engagement'].get('like_count'),
            'comments_count': row['engagement'].get('comments_count'),
            'rank_score': row['engagement']['rank_score'],
            'record_to': 'clips/%s.mov' % stem,
            'max_source_seconds': DEFAULT_MAX_SOURCE_SECONDS,
            'instruction': (
                'Open permalink while logged into Instagram, screen-record the Reel, '
                'save to record_to, then run reel_search.py accept-recordings.'
            ),
        })
    return {
        'schema_version': 1,
        'topic': topic,
        'account': account,
        'cue_id': cue_id,
        'edge': edge,
        'tags_searched': searched,
        'ranking': {
            'method': 'like_count + 5 * comments_count',
            'note': ('Hashtag API does not expose other creators\' view counts or '
                     'duration; apply <%ss after local recording.' %
                     DEFAULT_MAX_SOURCE_SECONDS),
        },
        'candidates': ranked,
        'record_queue': queue,
        'status': 'awaiting_screen_recordings',
        'destination': 'Instagram Reels splice insets',
    }


def probe_duration(path):
    """Return media duration in seconds via ffprobe."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        check=True, capture_output=True, text=True, timeout=30)
    value = float(result.stdout.strip())
    if value <= 0:
        raise ValueError('Invalid duration for %s' % path)
    return value


def accept_recordings(queue, recordings_dir, max_source_seconds=DEFAULT_MAX_SOURCE_SECONDS):
    """Keep only local recordings that exist and are under the short-clip gate."""
    root = Path(recordings_dir)
    accepted = []
    rejected = []
    for item in queue.get('record_queue', []):
        path = root / Path(item['record_to']).name
        if not path.is_file():
            # Also allow the relative path as written in the queue.
            alt = root / item['record_to']
            path = alt if alt.is_file() else path
        if not path.is_file():
            rejected.append({**item, 'reason': 'missing_recording', 'path': str(path)})
            continue
        try:
            duration = probe_duration(path)
        except (subprocess.CalledProcessError, ValueError, OSError) as exc:
            rejected.append({**item, 'reason': 'unreadable', 'detail': str(exc),
                             'path': str(path)})
            continue
        if duration > max_source_seconds:
            rejected.append({**item, 'reason': 'too_long', 'duration_seconds': duration,
                             'path': str(path)})
            continue
        accepted.append({
            **item,
            'path': str(path.resolve()),
            'duration_seconds': round(duration, 3),
            'rights_status': 'creator_permission_needed',
            'selection_basis': 'short_recorded_lead',
            'start_seconds': 0,
        })
    return {
        'schema_version': 1,
        'topic': queue.get('topic'),
        'account': queue.get('account', DEFAULT_ACCOUNT),
        'cue_id': queue.get('cue_id'),
        'max_source_seconds': max_source_seconds,
        'accepted': accepted,
        'rejected': rejected,
        'status': 'short_recordings_ready_for_rights_review' if accepted else 'no_short_recordings',
        'note': ('Accepted files are splice candidates only after rights/credit approval; '
                 'permalinks remain non-renderable.'),
    }


def catalog_from_accepted(accepted_bundle, topic=None):
    """Shape accepted short recordings as an Instagram catalog for pipeline.discover."""
    topic = topic or accepted_bundle.get('topic') or 'instagram reels'
    cue = accepted_bundle.get('cue_id') or 'evidence'
    candidates = []
    for row in accepted_bundle.get('accepted', []):
        candidates.append({
            'id': row['candidate_id'],
            'provider': 'instagram',
            'title': row.get('title') or row['candidate_id'],
            'page_url': row.get('permalink'),
            'direct_url': None,
            'rights_status': 'creator_permission_needed',
            'media_path': row['path'],
            'duration_seconds': row['duration_seconds'],
            'engagement': {
                'scope': 'recorded_short_lead',
                'like_count': row.get('like_count'),
                'comments_count': row.get('comments_count'),
                'rank_score': row.get('rank_score'),
            },
        })
    return {'cue_id': cue, 'topic': topic, 'candidates': candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    s = sub.add_parser('search', help='Topic → ranked Instagram Reel recording queue')
    s.add_argument('--topic', required=True)
    s.add_argument('--cue-id', default='evidence')
    s.add_argument('--tag', action='append', default=[], help='Extra hashtag (repeatable)')
    s.add_argument('--edge', choices=('top_media', 'recent_media'), default='top_media')
    s.add_argument('--limit', type=int, default=24)
    s.add_argument('--account', default=DEFAULT_ACCOUNT)
    s.add_argument('--output', required=True)

    a = sub.add_parser('accept-recordings',
                       help='Keep local screen recordings under the short-clip gate')
    a.add_argument('--queue', required=True, help='JSON from reel_search.py search')
    a.add_argument('--recordings-dir', required=True)
    a.add_argument('--max-source-seconds', type=float, default=DEFAULT_MAX_SOURCE_SECONDS)
    a.add_argument('--output', required=True)

    c = sub.add_parser('catalog', help='Convert accepted shorts into a pipeline catalog')
    c.add_argument('--accepted', required=True)
    c.add_argument('--output', required=True)

    args = parser.parse_args()
    if args.command == 'search':
        import os
        token = os.environ.get('META_ACCESS_TOKEN')
        user = os.environ.get('IG_USER_ID')
        if not token or not user:
            parser.error('META_ACCESS_TOKEN and IG_USER_ID required for live Reel search')
        version = os.environ.get('META_GRAPH_VERSION', 'v25.0')
        result = search_reels(
            args.topic, user, token, cue_id=args.cue_id, tags=args.tag or None,
            edge=args.edge, version=version, limit=args.limit, account=args.account)
    elif args.command == 'accept-recordings':
        queue = json.loads(Path(args.queue).read_text())
        result = accept_recordings(queue, args.recordings_dir, args.max_source_seconds)
    else:
        accepted = json.loads(Path(args.accepted).read_text())
        result = catalog_from_accepted(accepted)

    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
