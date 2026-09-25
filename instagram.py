"""Instagram professional-account discovery, publishing and measurement adapter.

Uses the official Graph API with Facebook Login. Discovery lists other creators'
posts as editorial leads; it never downloads, stores, or licenses their video.
Publishing requires an explicitly approved release manifest and a public HTTPS
URL to our rendered Reel. A small ledger prevents accidental double submission.
"""
import argparse
import hashlib
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from studio import digest


def graph(method, path, token, params=None, version='v25.0'):
    if not version.startswith('v') or not version[1:].replace('.', '').isdigit():
        raise ValueError('Invalid Graph API version')
    base = 'https://graph.facebook.com/' + version + '/' + path.lstrip('/')
    params = params or {}
    if method == 'GET':
        url = base + '?' + urllib.parse.urlencode(params)
        data = None
    else:
        url = base
        data = urllib.parse.urlencode(params).encode()
    request = urllib.request.Request(url, data=data, method=method,
                                     headers={'Authorization': 'Bearer ' + token,
                                              'User-Agent': 'BioticaMedia/0.1'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


HASHTAG_MEDIA_FIELDS = (
    'id,caption,media_type,permalink,timestamp,like_count,comments_count'
)


def _engagement_score(likes, comments):
    """Proxy score for hashtag leads; not a view count and not causal."""
    like_n = likes if isinstance(likes, int) and likes >= 0 else 0
    comment_n = comments if isinstance(comments, int) and comments >= 0 else 0
    return like_n + 5 * comment_n


def discover_hashtag(tag, ig_user_id, token, version='v25.0', edge='top_media'):
    """Find public hashtag VIDEO leads for editorial review, never clip downloads."""
    tag = tag.strip().lstrip('#')
    if not tag or ' ' in tag:
        raise ValueError('One hashtag is required')
    if edge not in ('top_media', 'recent_media'):
        raise ValueError('edge must be top_media or recent_media')
    ids = graph('GET', 'ig_hashtag_search', token,
                {'user_id': ig_user_id, 'q': tag}, version).get('data', [])
    if not ids:
        return {'tag': tag, 'edge': edge, 'candidates': []}
    response = graph('GET', str(ids[0]['id']) + '/' + edge, token, {
        'user_id': ig_user_id,
        'fields': HASHTAG_MEDIA_FIELDS,
        'limit': 50,
    }, version)
    rows = []
    for item in response.get('data', []):
        if item.get('media_type') != 'VIDEO':
            continue
        likes = item.get('like_count')
        comments = item.get('comments_count')
        rows.append({
            'id': 'instagram:' + item['id'], 'provider': 'instagram',
            'title': (item.get('caption') or '')[:180],
            'page_url': item.get('permalink'), 'direct_url': None,
            'timestamp': item.get('timestamp'),
            'rights_status': 'creator_permission_needed',
            'engagement': {
                'scope': 'hashtag_' + edge,
                'like_count': likes,
                'comments_count': comments,
                'rank_score': _engagement_score(likes, comments),
                'note': ('Hashtag ranking uses likes/comments when present; '
                         'view counts and duration require local review'),
            },
            'tag': tag,
        })
    rows.sort(key=lambda row: row['engagement']['rank_score'], reverse=True)
    return {'tag': tag, 'edge': edge, 'candidates': rows}


def validate_release(release):
    """A reviewed file and matching public URL are required before creating a post."""
    required = ['status', 'reviewer', 'file', 'file_sha256', 'public_video_url',
                'caption', 'script_sha256', 'footage_plan_sha256']
    if any(not release.get(k) for k in required) or release['status'] != 'approved_for_publication':
        raise ValueError('Complete publication approval manifest required')
    path = Path(release['file'])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != release['file_sha256']:
        raise ValueError('Approved rendered file missing or changed')
    url = urllib.parse.urlparse(release['public_video_url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('Meta needs an accessible HTTPS video URL')
    if len(release['caption']) > 2200:
        raise ValueError('Caption too long')
    return digest(release)


def create_container(release, ledger, ig_user_id, token, version='v25.0'):
    """Submit once; an ambiguous failure remains unknown until reconciled."""
    job = validate_release(release)
    with sqlite3.connect(ledger) as db:
        db.execute('CREATE TABLE IF NOT EXISTS posts (job TEXT PRIMARY KEY, state TEXT, '
                   'container TEXT, media TEXT, created TEXT)')
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT 1 FROM posts WHERE job=?', (job,)).fetchone():
            raise ValueError('Release already submitted; inspect ledger before retry')
        db.execute('INSERT INTO posts VALUES (?,?,?,?,?)',
                   (job, 'submitting_or_unknown', None, None, datetime.now(timezone.utc).isoformat()))
        db.commit()
        result = graph('POST', ig_user_id + '/media', token, {
            'media_type': 'REELS', 'video_url': release['public_video_url'],
            'caption': release['caption'], 'share_to_feed': 'true',
        }, version)
        if not result.get('id'):
            raise ValueError('No container ID; inspect Meta account before retry')
        db.execute('UPDATE posts SET state=?, container=? WHERE job=?',
                   ('container_created', result['id'], job))
        db.commit()
        return {'job': job, 'container_id': result['id'], 'state': 'container_created'}


def publish_container(job, ledger, ig_user_id, token, version='v25.0'):
    """Check processing then publish once; never blindly retry an unknown outcome."""
    with sqlite3.connect(ledger) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT state,container FROM posts WHERE job=?', (job,)).fetchone()
        if not row or row[0] != 'container_created':
            raise ValueError('Container missing or publish already attempted')
        state, container = row
        status = graph('GET', container, token, {'fields': 'status_code,status'}, version)
        if status.get('status_code') != 'FINISHED':
            db.rollback()
            return {'job': job, 'state': 'awaiting_processing', 'provider_status': status}
        db.execute('UPDATE posts SET state=? WHERE job=? AND state=?',
                   ('publishing_or_unknown', job, 'container_created'))
        db.commit()
        result = graph('POST', ig_user_id + '/media_publish', token,
                       {'creation_id': container}, version)
        if not result.get('id'):
            raise ValueError('Publication outcome unknown; reconcile with Instagram')
        db.execute('UPDATE posts SET state=?, media=? WHERE job=?',
                   ('published', result['id'], job))
        db.commit()
        return {'job': job, 'media_id': result['id'], 'state': 'published'}


def insights(job, ledger, token, version='v25.0'):
    """Capture a dated snapshot of *our* Reel metrics with provenance."""
    with sqlite3.connect(ledger) as db:
        row = db.execute('SELECT state,media FROM posts WHERE job=?', (job,)).fetchone()
    if not row or row[0] != 'published':
        raise ValueError('Published media ID required')
    metrics = 'views,reach,likes,comments,shares,saved,ig_reels_avg_watch_time'
    result = graph('GET', row[1] + '/insights', token, {'metric': metrics}, version)
    return {'job': job, 'media_id': row[1], 'retrieved_at': datetime.now(timezone.utc).isoformat(),
            'provider': 'Instagram Graph API', 'metrics': result.get('data', []),
            'note': 'Own-Reel aggregate metrics; no segment-level retention or causal A/B claim'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('discover')
    d.add_argument('--tag', required=True)
    d.add_argument('--cue-id', required=True, help='Reviewed script beat for this hashtag')
    d.add_argument('--edge', choices=('top_media', 'recent_media'), default='top_media')
    d.add_argument('--output', required=True)
    c = sub.add_parser('create')
    c.add_argument('--release', required=True)
    c.add_argument('--ledger', required=True)
    u = sub.add_parser('publish')
    u.add_argument('--job', required=True)
    u.add_argument('--ledger', required=True)
    i = sub.add_parser('insights')
    i.add_argument('--job', required=True)
    i.add_argument('--ledger', required=True)
    i.add_argument('--output', required=True)
    args = p.parse_args()
    token, user = os.environ.get('META_ACCESS_TOKEN'), os.environ.get('IG_USER_ID')
    if not token or not user:
        p.error('META_ACCESS_TOKEN and IG_USER_ID required for live Graph API')
    version = os.environ.get('META_GRAPH_VERSION', 'v25.0')
    if args.command == 'discover':
        result = discover_hashtag(args.tag, user, token, version, edge=args.edge)
        result['cue_id'] = args.cue_id
    elif args.command == 'create':
        result = create_container(json.loads(Path(args.release).read_text()),
                                  args.ledger, user, token, version)
    elif args.command == 'publish':
        result = publish_container(args.job, args.ledger, user, token, version)
    else:
        result = insights(args.job, args.ledger, token, version)
    if getattr(args, 'output', None):
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, indent=2) + '\n')
        print(path)
    else:
        print(json.dumps(result))


if __name__ == '__main__':
    main()
