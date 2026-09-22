"""Topic footage discovery, rights-gated segment planning, and local assembly.

YouTube is a discovery source only. This module never downloads YouTube media.
An editor supplies an approved direct file URL or local master plus a license
record. Owner-supplied retention samples, when present, identify the strongest
measured windows; absent those samples, timestamps must be chosen by an editor.
"""
import argparse
import json
import math
import os
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

USER_AGENT = 'BioticaFootageResearch/0.1 (editorial contact: see repository)'
YOUTUBE_HOSTS = {'youtube.com', 'www.youtube.com', 'm.youtube.com', 'youtu.be',
                 'googlevideo.com', 'www.googlevideo.com'}


def fetch_json(base, params):
    """Read bounded metadata from a documented public API, not video bytes."""
    url = base + '?' + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def discover_commons(topic, limit=20):
    """Return directly linked video candidates with license metadata for review."""
    payload = fetch_json('https://commons.wikimedia.org/w/api.php', {
        'action': 'query', 'format': 'json', 'generator': 'search',
        'gsrsearch': topic + ' filetype:video', 'gsrnamespace': '6',
        'gsrlimit': min(limit, 50), 'prop': 'imageinfo',
        'iiprop': 'url|mime|extmetadata', 'iilimit': '1',
    })
    candidates = []
    for page in payload.get('query', {}).get('pages', {}).values():
        info = (page.get('imageinfo') or [{}])[0]
        if not info.get('mime', '').startswith('video/') or not info.get('url'):
            continue
        meta = info.get('extmetadata', {})
        field = lambda name: meta.get(name, {}).get('value', '')
        candidates.append({
            'id': 'commons:' + str(page['pageid']), 'provider': 'commons',
            'title': page['title'].removeprefix('File:'),
            'page_url': 'https://commons.wikimedia.org/wiki/' +
                        urllib.parse.quote(page['title'].replace(' ', '_')),
            'direct_url': info['url'], 'license_name': field('LicenseShortName'),
            'license_url': field('LicenseUrl'), 'credit_html': field('Credit'),
            'artist_html': field('Artist'), 'rights_status': 'review_required',
            'engagement': None,
        })
    return candidates


def discover_youtube(topic, api_key, limit=20):
    """Find whole-video leads. No segment analytics or downloadable file exists here."""
    found = fetch_json('https://www.googleapis.com/youtube/v3/search', {
        'part': 'snippet', 'q': topic, 'type': 'video',
        'maxResults': min(limit, 50), 'key': api_key,
    }).get('items', [])
    ids = [item['id']['videoId'] for item in found]
    if not ids:
        return []
    details = fetch_json('https://www.googleapis.com/youtube/v3/videos', {
        'part': 'statistics,status,snippet', 'id': ','.join(ids), 'key': api_key,
    }).get('items', [])
    by_id = {item['id']: item for item in details}
    candidates = []
    for vid in ids:
        data = by_id.get(vid, {})
        stats = data.get('statistics', {})
        candidates.append({
            'id': 'youtube:' + vid, 'provider': 'youtube',
            'title': data.get('snippet', {}).get('title', ''),
            'page_url': 'https://www.youtube.com/watch?v=' + vid,
            'direct_url': None, 'rights_status': 'creator_permission_needed',
            'engagement': {'scope': 'whole_video',
                           'views': stats.get('viewCount'),
                           'likes': stats.get('likeCount'),
                           'comments': stats.get('commentCount')},
            'youtube_license': data.get('status', {}).get('license'),
        })
    return candidates


def discover(topic, youtube_key=None, limit=20):
    if not topic.strip():
        raise ValueError('Topic is required')
    records = discover_commons(topic, limit)
    if youtube_key:
        records.extend(discover_youtube(topic, youtube_key, limit))
    return {'schema_version': 1, 'topic': topic, 'candidates': records,
            'note': 'Search popularity is not segment retention or reuse permission.'}


def safe_media_source(source):
    """Reject YouTube URLs and insecure remote sources before FFmpeg sees them."""
    source = str(source)
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in ('http', 'https'):
        host = (parsed.hostname or '').lower()
        if parsed.scheme != 'https' or host in YOUTUBE_HOSTS or \
                host.endswith(('.youtube.com', '.googlevideo.com', '.youtu.be')):
            raise ValueError('Remote media must be HTTPS and outside YouTube')
        if not host or parsed.username or parsed.password:
            raise ValueError('Invalid remote media URL')
    elif parsed.scheme or not Path(source).is_file():
        raise ValueError('Media must be an existing local file or HTTPS direct file URL')
    return source


def best_window(samples, length=5):
    """Choose a maximal mean owner-measured retention window at 1-second resolution.

    `samples` is [{second: 0, watch_ratio: 0.8}, ...]. Missing seconds disqualify
    a window. This is actual source-video engagement, not an inferred visual score.
    """
    values = {}
    for row in samples:
        sec, ratio = row['second'], row['watch_ratio']
        if type(sec) is not int or sec < 0 or not isinstance(ratio, (int, float)) \
                or not math.isfinite(ratio) or ratio < 0 or sec in values:
            raise ValueError('Invalid or duplicate retention sample')
        values[sec] = ratio
    windows = [(sum(values[t] for t in range(start, start + length)) / length, start)
               for start in values if all(t in values for t in range(start, start + length))]
    if not windows:
        raise ValueError('No continuous retention window of requested length')
    score, start = max(windows, key=lambda x: (x[0], -x[1]))
    return start, round(score, 5)


def plan(catalog, approvals, target_seconds=30, segment_seconds=5):
    """Build exact-duration shot list only from separately reviewed master files.

    Approvals are explicit editorial records. They may refer to a YouTube lead,
    but its media_source must be supplied separately by the owner/licensor.
    """
    if type(target_seconds) is not int or type(segment_seconds) is not int \
            or target_seconds <= 0 or segment_seconds <= 0 \
            or target_seconds % segment_seconds:
        raise ValueError('Target must be a positive multiple of segment duration')
    catalog_ids = {c['id'] for c in catalog['candidates']}
    shots = []
    for item in approvals:
        if item['candidate_id'] not in catalog_ids or item.get('rights_status') != 'approved':
            raise ValueError('Candidate missing or reuse rights not approved')
        if not item.get('license_basis') or not item.get('credit') or not item.get('media_source'):
            raise ValueError('Approval needs license basis, credit and direct media source')
        source = safe_media_source(item['media_source'])
        if 'retention_samples' in item:
            start, ratio = best_window(item['retention_samples'], segment_seconds)
            basis = 'owner_supplied_retention'
        elif 'start_seconds' in item:
            start, ratio, basis = item['start_seconds'], None, 'editor_selected'
            if not isinstance(start, (int, float)) or not math.isfinite(start) or start < 0:
                raise ValueError('Invalid start time')
        else:
            raise ValueError('Need owner retention samples or editor-selected start time')
        shots.append({'candidate_id': item['candidate_id'], 'media_source': source,
                      'start_seconds': start, 'duration_seconds': segment_seconds,
                      'selection_basis': basis, 'watch_ratio': ratio,
                      'license_basis': item['license_basis'], 'credit': item['credit'],
                      'script_cue': item.get('script_cue', ''),
                      'destination_seconds': len(shots) * segment_seconds})
    if len(shots) != target_seconds // segment_seconds:
        raise ValueError('Need exactly %d approved segments' % (target_seconds // segment_seconds))
    return {'schema_version': 1, 'topic': catalog['topic'],
            'target_seconds': target_seconds, 'shots': shots,
            'status': 'renderable_not_publish_approved',
            'note': 'Owner retention measures source attention, not inset performance.'}


def run_ffmpeg(args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', '-y',
                    *args], check=True, timeout=300)


def render(plan_data, output, host=None):
    """Seek and transcode only selected windows where direct source permits it.

    Remote seeking can still transfer more than the five-second payload: MP4
    indexes, keyframe positions, server range support and FFmpeg behavior vary.
    Review transfer charges and original rights before running remote inputs.
    """
    if plan_data.get('status') != 'renderable_not_publish_approved':
        raise ValueError('Expected a rights-gated production plan')
    import tempfile
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='bioticaclip-') as temp:
        temp = Path(temp)
        clips = []
        for index, shot in enumerate(plan_data['shots']):
            source = safe_media_source(shot['media_source'])
            clip = temp / ('clip%02d.mp4' % index)
            # Input-side -ss asks FFmpeg to seek before decoding the selected span.
            run_ffmpeg(['-ss', str(shot['start_seconds']), '-i', source,
                        '-t', str(shot['duration_seconds']), '-an',
                        '-vf', 'scale=640:360:force_original_aspect_ratio=decrease,'
                               'pad=640:360:(ow-iw)/2:(oh-ih)/2',
                        '-r', '30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(clip)])
            clips.append(clip)
        listing = temp / 'concat.txt'
        listing.write_text(''.join("file '%s'\n" % clip for clip in clips))
        strip = temp / 'inset.mp4'
        run_ffmpeg(['-f', 'concat', '-safe', '0', '-i', str(listing),
                    '-c', 'copy', str(strip)])
        if host:
            host = safe_media_source(host)
            run_ffmpeg(['-i', host, '-i', str(strip), '-filter_complex',
                        '[0:v][1:v]overlay=W-w-32:150:shortest=1[v]',
                        '-map', '[v]', '-map', '0:a?', '-t', str(plan_data['target_seconds']),
                        '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(output)])
        else:
            run_ffmpeg(['-i', str(strip), '-c', 'copy', str(output)])
    return output


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    d = sub.add_parser('discover')
    d.add_argument('--topic', required=True)
    d.add_argument('--youtube', action='store_true', help='Use YOUTUBE_API_KEY for discovery only')
    d.add_argument('--output', required=True)
    q = sub.add_parser('plan')
    q.add_argument('--catalog', required=True)
    q.add_argument('--approvals', required=True)
    q.add_argument('--output', required=True)
    r = sub.add_parser('render')
    r.add_argument('--plan', required=True)
    r.add_argument('--output', required=True)
    r.add_argument('--host', help='Locally supplied Runway avatar video')
    args = p.parse_args()
    if args.command == 'discover':
        key = os.environ.get('YOUTUBE_API_KEY') if args.youtube else None
        if args.youtube and not key:
            p.error('YOUTUBE_API_KEY required for YouTube discovery')
        result = discover(args.topic, key)
    elif args.command == 'plan':
        result = plan(json.loads(Path(args.catalog).read_text()),
                      json.loads(Path(args.approvals).read_text())['approvals'])
    else:
        print(render(json.loads(Path(args.plan).read_text()), args.output, args.host))
        return
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
