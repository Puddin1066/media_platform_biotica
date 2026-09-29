"""Build and validate an Instagram Reel release manifest (never auto-publishes).

Film → AI preview stays unreviewed/private. This helper only prepares the
explicit `approved_for_publication` packet that `instagram.py create` requires.
Publication still needs a separate live create/publish call after human review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from studio import digest


REQUIRED = (
    'status', 'reviewer', 'file', 'file_sha256', 'public_video_url',
    'caption', 'script_sha256', 'footage_plan_sha256',
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_release(
    file: str,
    public_video_url: str,
    caption: str,
    reviewer: str,
    script_sha256: str,
    footage_plan_sha256: str,
    *,
    status: str = 'approved_for_publication',
) -> dict:
    path = Path(file)
    if not path.is_file():
        raise ValueError('Rendered Reel file is missing')
    if status != 'approved_for_publication':
        raise ValueError('Release status must be approved_for_publication')
    if not reviewer.strip():
        raise ValueError('Reviewer is required')
    if not caption.strip():
        raise ValueError('Caption is required')
    if len(caption) > 2200:
        raise ValueError('Caption too long')
    if not public_video_url.startswith('https://'):
        raise ValueError('public_video_url must be HTTPS')
    release = {
        'status': status,
        'reviewer': reviewer.strip(),
        'file': str(path.resolve()),
        'file_sha256': file_sha256(path),
        'public_video_url': public_video_url.strip(),
        'caption': caption.strip(),
        'script_sha256': script_sha256.strip(),
        'footage_plan_sha256': footage_plan_sha256.strip(),
    }
    release['release_sha256'] = digest(release)
    return release


def validate_release_packet(release: dict) -> dict:
    missing = [k for k in REQUIRED if not release.get(k)]
    if missing:
        raise ValueError('Release missing fields: ' + ', '.join(missing))
    if release['status'] != 'approved_for_publication':
        raise ValueError('Release is not approved_for_publication')
    path = Path(release['file'])
    if not path.is_file():
        raise ValueError('Release file path is not readable')
    actual = file_sha256(path)
    if actual != release['file_sha256']:
        raise ValueError('file_sha256 does not match local file bytes')
    return {
        'ok': True,
        'file': str(path),
        'file_sha256': actual,
        'public_video_url': release['public_video_url'],
        'reviewer': release['reviewer'],
        'caption_chars': len(release['caption']),
        'publishable': True,
        'note': 'Validated locally only; run instagram.py create/publish to post',
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)

    b = sub.add_parser('build', help='Write an approved_for_publication JSON packet')
    b.add_argument('--file', required=True, help='Local rendered MP4/MOV')
    b.add_argument('--public-video-url', required=True, help='Public HTTPS URL Meta can fetch')
    b.add_argument('--caption', required=True)
    b.add_argument('--reviewer', required=True)
    b.add_argument('--script-sha256', required=True)
    b.add_argument('--footage-plan-sha256', required=True)
    b.add_argument('--output', required=True)

    v = sub.add_parser('validate', help='Validate a release packet without posting')
    v.add_argument('--release', required=True)
    v.add_argument('--output')

    args = p.parse_args()
    if args.command == 'build':
        release = build_release(
            args.file, args.public_video_url, args.caption, args.reviewer,
            args.script_sha256, args.footage_plan_sha256)
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(release, indent=2) + '\n', encoding='utf-8')
        print(out)
    else:
        release = json.loads(Path(args.release).read_text(encoding='utf-8'))
        result = validate_release_packet(release)
        text = json.dumps(result, indent=2) + '\n'
        if args.output:
            Path(args.output).write_text(text, encoding='utf-8')
            print(args.output)
        else:
            print(text, end='')


if __name__ == '__main__':
    main()
