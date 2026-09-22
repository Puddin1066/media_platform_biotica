"""Optional Runway speech and Act-Two jobs with durable, explicit submissions.

The live commands can incur charges. Each invocation records a reservation before
submitting. An ambiguous failure stays reserved, preventing accidental repeat
charges. `collect` retrieves a known task exactly once into private local media.
Neither command publishes a Reel or accepts an Instagram/YouTube media URL.
"""
import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

from remotion_handoff import duration
from studio import digest

BEATS = ('opening', 'explanations', 'evidence', 'limits', 'next_test')


def client_from_environment():
    if os.environ.get('RUNWAY_LIVE_ENABLED') != 'true' or \
            not os.environ.get('RUNWAYML_API_SECRET'):
        raise ValueError('Configure RUNWAY_LIVE_ENABLED=true and RUNWAYML_API_SECRET privately')
    from runwayml import RunwayML  # Optional pinned dependency, imported only for live calls.
    return RunwayML(api_key=os.environ['RUNWAYML_API_SECRET'], max_retries=0)


def reserve(root, specification):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (digest(specification) + '.json')
    with path.open('x', encoding='utf-8') as out:
        json.dump({'state': 'reserved_unknown', 'specification': specification}, out, indent=2)
    return path


def update(path, record):
    Path(path).write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


def submit_tts(board, beat, voice_id, root, client=None, live=False):
    if board.get('status') != 'awaiting_footage' or beat not in BEATS or \
            [c.get('cue_id') for c in board.get('cues', [])] != list(BEATS):
        raise ValueError('Reviewed storyboard and valid beat required')
    if not voice_id or not voice_id.strip():
        raise ValueError('Runway preset voice ID required')
    text = board['cues'][BEATS.index(beat)]['spoken_text']
    if not text or len(text) > 1000:
        raise ValueError('Beat is empty or exceeds the speech model character limit')
    spec = {'kind': 'tts', 'script_sha256': board['script_sha256'], 'beat': beat,
            'voice_id': voice_id, 'text': text, 'model': 'eleven_multilingual_v2'}
    if not live:
        return {'state': 'dry_run', 'specification': spec}
    client = client or client_from_environment()
    path = reserve(root, spec)
    task = client.text_to_speech.create(model='eleven_multilingual_v2', prompt_text=text,
                                       voice={'type': 'runway-preset', 'preset_id': voice_id})
    record = {'state': 'submitted', 'task_id': task.id, 'specification': spec}
    update(path, record)
    return {'record': str(path), **record}


def submit_act_two(character, performance, root, client=None, live=False):
    """Animate a supplied character plate using a separate filmed performance.

    Act Two requires a *performance video*; an audio-only narration cannot
    provide the performance reference. Source footage must belong to the owner.
    """
    character, performance = Path(character), Path(performance)
    if not character.is_file() or not performance.is_file() or \
            character.suffix.lower() != '.mp4' or performance.suffix.lower() != '.mp4':
        raise ValueError('Character plate and performance must be local MP4 files')
    if not 3 <= duration(performance) <= 30:
        raise ValueError('Act Two performance video must run 3–30 seconds')
    spec = {'kind': 'act_two', 'character_sha256': digest_file(character),
            'performance_sha256': digest_file(performance), 'model': 'act_two'}
    if not live:
        return {'state': 'dry_run', 'specification': spec}
    client = client or client_from_environment()
    path = reserve(root, spec)
    with character.open('rb') as data:
        character_uri = client.uploads.create_ephemeral(file=data).uri
    with performance.open('rb') as data:
        performance_uri = client.uploads.create_ephemeral(file=data).uri
    task = client.character_performance.create(
        model='act_two', character={'type': 'video', 'uri': character_uri},
        reference={'type': 'video', 'uri': performance_uri}, ratio='720:1280')
    record = {'state': 'submitted', 'task_id': task.id, 'specification': spec}
    update(path, record)
    return {'record': str(path), **record}


def submit_avatar(avatar_id, audio, root, client=None, live=False):
    """Render a configured Runway custom avatar speaking the approved audio.

    This generates a new avatar shot, separate from the reusable cycling plate.
    The account must already contain the avatar; creation is a separate step.
    """
    audio = Path(audio)
    if not avatar_id or not audio.is_file() or audio.suffix.lower() not in {'.mp3', '.wav', '.m4a'}:
        raise ValueError('Custom avatar ID and local narration file required')
    if not 0 < duration(audio) <= 30:
        raise ValueError('Avatar narration must be no longer than 30 seconds')
    spec = {'kind': 'avatar', 'avatar_id': avatar_id,
            'audio_sha256': digest_file(audio), 'model': 'gwm1_avatars'}
    if not live:
        return {'state': 'dry_run', 'specification': spec}
    client = client or client_from_environment()
    path = reserve(root, spec)
    with audio.open('rb') as data:
        audio_uri = client.uploads.create_ephemeral(file=data).uri
    task = client.avatar_videos.create(
        model='gwm1_avatars', avatar={'type': 'custom', 'avatar_id': avatar_id},
        speech={'type': 'audio', 'audio': audio_uri})
    record = {'state': 'submitted', 'task_id': task.id, 'specification': spec}
    update(path, record)
    return {'record': str(path), **record}


def digest_file(path):
    import hashlib
    h = hashlib.sha256()
    with Path(path).open('rb') as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def download_output(url, destination):
    """Bound a provider output download and keep its URL out of manifests/logs."""
    if urllib.parse.urlparse(url).scheme != 'https':
        raise ValueError('Provider output must use HTTPS')
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_suffix(destination.suffix + '.part')
    try:
        with urllib.request.urlopen(url, timeout=60) as source, part.open('wb') as out:
            if urllib.parse.urlparse(source.geturl()).scheme != 'https':
                raise ValueError('Provider download redirected away from HTTPS')
            size = 0
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > 250 * 1024 * 1024:
                    raise ValueError('Runway output exceeds 250 MB')
                out.write(chunk)
        if size == 0:
            raise ValueError('Empty provider output')
        part.replace(destination)
    finally:
        part.unlink(missing_ok=True)


def collect(record_path, destination, client=None):
    record_path = Path(record_path)
    record = json.loads(record_path.read_text())
    if record.get('state') != 'submitted' or not record.get('task_id'):
        raise ValueError('Submitted task record required; completed tasks cannot be collected twice')
    client = client or client_from_environment()
    task = client.tasks.retrieve(record['task_id'])
    if task.status == 'SUCCEEDED':
        if not task.output:
            raise ValueError('Runway task succeeded without a downloadable output')
        download_output(task.output[0], destination)
        record.update(state='collected', file=str(destination), file_sha256=digest_file(destination))
        update(record_path, record)
    elif task.status in {'FAILED', 'CANCELLED'}:
        record['state'] = task.status.lower()
        update(record_path, record)
    return {'state': record['state'], 'task_id': record['task_id'],
            'file': record.get('file')}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    tts = sub.add_parser('submit-tts')
    tts.add_argument('--storyboard', required=True)
    tts.add_argument('--beat', required=True, choices=BEATS)
    tts.add_argument('--voice-id', required=True)
    tts.add_argument('--ledger', default='outputs/runway')
    tts.add_argument('--live', action='store_true')
    act = sub.add_parser('submit-act-two')
    act.add_argument('--character', required=True)
    act.add_argument('--performance', required=True)
    act.add_argument('--ledger', default='outputs/runway')
    act.add_argument('--live', action='store_true')
    avatar = sub.add_parser('submit-avatar')
    avatar.add_argument('--avatar-id', required=True)
    avatar.add_argument('--audio', required=True)
    avatar.add_argument('--ledger', default='outputs/runway')
    avatar.add_argument('--live', action='store_true')
    get = sub.add_parser('collect')
    get.add_argument('--record', required=True)
    get.add_argument('--output', required=True)
    args = p.parse_args()
    if args.command == 'submit-tts':
        result = submit_tts(json.loads(Path(args.storyboard).read_text()), args.beat,
                            args.voice_id, args.ledger, live=args.live)
    elif args.command == 'submit-act-two':
        result = submit_act_two(args.character, args.performance, args.ledger, live=args.live)
    elif args.command == 'submit-avatar':
        result = submit_avatar(args.avatar_id, args.audio, args.ledger, live=args.live)
    else:
        result = collect(args.record, args.output)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
