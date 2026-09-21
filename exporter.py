"""Readable, offline production packets. No provider calls or publication.

Exports are planning documents until writers and renderers are implemented.
The manifest explicitly distinguishes proposed destinations from uploaded files.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from studio import FORMATS, compile_package, validate

DESTINATIONS = {
    'short': ['TikTok', 'Instagram Reels', 'YouTube Shorts'],
    'podcast': ['Podcast host / RSS'],
    'investigation': ['YouTube'],
    'newsletter': ['Substack (manual editorial publication)'],
    'book': ['Private manuscript archive'],
    'treatment': ['Private screenplay / producer-pitch archive'],
}


def files_for(packet, name):
    """Build all bytes before writing; source records stay separate from prose."""
    package = compile_package(packet, name)
    heading = '# BLOCKED PREVIEW — NOT FOR PUBLICATION\n\n'
    script = heading + packet['question'] + '\n\n'
    script += 'This is an unfilled editorial outline, not generated narration.\n\n'
    for beat in package['beats']:
        script += '## ' + beat['purpose'].title() + '\n\n[Awaiting sourced writing and review]\n\n'
    plan = heading + '## Mystery requirements\n\n'
    for item in ['Evidence of a real anomaly', 'Personal stakes for the audience',
                 'Competing explanations', 'Discriminating test', 'Earned payoff', 'Remaining question']:
        plan += '- [ ] ' + item + '\n'
    plan += '\n## Proposed destinations (nothing uploaded)\n\n' + '\n'.join(DESTINATIONS[name])
    plan += '\n\n## Media status\n\nNo video, audio, captions or final copy rendered.\n'
    notes = heading + '## Source inventory\n\n' + json.dumps(packet['sources'], indent=2)
    notes += '\n\n## Hypotheses — not conclusions\n\n' + json.dumps(packet['hypotheses'], indent=2)
    files = {
        'outline.md': script, 'production-plan.md': plan, 'source-notes.md': notes,
        'package.json': json.dumps(package, indent=2) + '\n',
    }
    manifest = {
        'export_schema_version': 1, 'run_id': package['run_id'],
        'status': 'blocked_preview', 'publishable': False, 'uploaded': False,
        'destinations': DESTINATIONS[name], 'api_calls': 0,
        'sha256': {p: hashlib.sha256(v.encode()).hexdigest() for p, v in files.items()},
    }
    files['manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    return package['run_id'], files


def export(packet, name, root):
    """Content-addressed folders; retries cannot silently replace edited files.

    This local writer is single-process. A future hosted worker must add locking
    and atomic directory commits before supporting concurrent exports.
    """
    key, files = files_for(validate(packet), name)
    # Include the exporter bytes in identity so a new export layout gets a new folder.
    layout_hash = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    directory = Path(root) / name / layout_hash
    directory.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        path = directory / filename
        if path.exists() and path.read_text(encoding='utf-8') != content:
            raise ValueError('Existing export was edited; refusing overwrite')
    for filename, content in files.items():
        path = directory / filename
        if not path.exists():
            with path.open('x', encoding='utf-8') as handle:
                handle.write(content)
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', default='cases/mens-health.json')
    parser.add_argument('--format', choices=[*FORMATS, 'all'], default='all')
    parser.add_argument('--output', default='outputs/packages')
    args = parser.parse_args()
    packet = json.loads(Path(args.case).read_text(encoding='utf-8'))
    for name in FORMATS if args.format == 'all' else [args.format]:
        print(export(packet, name, args.output))
