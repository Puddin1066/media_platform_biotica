"""Operate one private Satoshi episode without re-submitting paid jobs.

Audio beats can be submitted to Runway concurrently. The host is an independent
plate, an Act Two performance, or a custom avatar created after narration is
assembled. Reviewed source excerpts stay local; Remotion makes the final Reel.
The default commands inspect or dry-run and never publish anything.
"""
import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import production_job
import runway_media
from speech_timing import BEATS, assemble
from studio import digest


def inputs(root):
    root = Path(root).resolve(strict=True)
    board = json.loads((root / 'storyboard.json').read_text(encoding='utf-8'))
    plan = json.loads((root / 'footage-plan.json').read_text(encoding='utf-8'))
    if board.get('status') != 'awaiting_footage' or \
            [c.get('cue_id') for c in board.get('cues', [])] != list(BEATS):
        raise ValueError('Five-beat reviewed storyboard required')
    if plan.get('status') != 'renderable_not_publish_approved' or \
            plan.get('script_sha256') != board.get('script_sha256') or \
            len(plan.get('shots', [])) != 6:
        raise ValueError('Matching six-shot reviewed footage plan required')
    for shot in plan['shots']:
        source = Path(shot['media_source'])
        if source.is_absolute() or not (root / source).resolve().is_relative_to(root):
            raise ValueError('Footage must use private relative paths within the episode')
        if not (root / source).is_file() or not shot.get('license_basis') or \
                not shot.get('credit'):
            raise ValueError('Footage source, rights basis and credit required')
    return root, board


def beat_file(root, beat):
    return next((p for ext in ('.wav', '.mp3', '.m4a')
                 if (p := root / 'audio' / (beat + ext)).is_file()), None)


def record_for(root, spec):
    return root / 'generated' / 'runway' / (digest(spec) + '.json')


def status(root):
    root, board = inputs(root)
    return {'episode': str(root), 'script_sha256': board['script_sha256'],
            'audio': {beat: ('ready' if beat_file(root, beat) else 'missing') for beat in BEATS},
            'host': 'ready' if (root / 'plate.mp4').is_file() or
                    (root / 'generated' / 'host.mp4').is_file() else 'missing',
            'footage': 'six reviewed local sources',
            'render': 'ready' if all(beat_file(root, b) for b in BEATS) and
                      ((root / 'plate.mp4').is_file() or
                       (root / 'generated' / 'host.mp4').is_file()) else 'needs_assets',
            'publishable': False}


def submit_audio(root, voice_id, live=False, workers=5):
    """Start only absent beats; ledger identity prevents double billing on retry.

    A reserved_unknown record means the provider outcome requires reconciliation.
    It is returned to the operator, never silently re-submitted.
    """
    root, board = inputs(root)
    if not 1 <= workers <= 5:
        raise ValueError('Use 1–5 simultaneous Runway speech jobs')

    def one(beat):
        if beat_file(root, beat):
            return beat, {'state': 'audio_ready'}
        preview = runway_media.submit_tts(board, beat, voice_id, root / 'generated' / 'runway')
        path = record_for(root, preview['specification'])
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            return beat, {'state': record['state'], 'record': str(path),
                          'task_id': record.get('task_id')}
        if not live:
            return beat, preview
        return beat, runway_media.submit_tts(board, beat, voice_id,
                                             root / 'generated' / 'runway', live=True)

    result = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, beat) for beat in BEATS]
        for future in as_completed(futures):
            beat, item = future.result()
            result[beat] = item
    return {beat: result[beat] for beat in BEATS}


def collect_audio(root, voice_id):
    root, board = inputs(root)
    result = {}
    for beat in BEATS:
        if beat_file(root, beat):
            result[beat] = 'audio_ready'
            continue
        spec = runway_media.submit_tts(board, beat, voice_id, root / 'generated' / 'runway')
        record = record_for(root, spec['specification'])
        if not record.is_file():
            result[beat] = 'not_submitted'
            continue
        data = json.loads(record.read_text(encoding='utf-8'))
        if data['state'] == 'submitted':
            result[beat] = runway_media.collect(record, root / 'audio' / (beat + '.mp3'))['state']
        else:
            result[beat] = data['state']
    return result


def narration(root):
    root, board = inputs(root)
    files = {beat: beat_file(root, beat) for beat in BEATS}
    if any(path is None for path in files.values()):
        raise ValueError('Collect or record all five audio beats before assembling narration')
    generated = root / 'generated'
    assemble(board, files, generated / 'narration.wav', generated / 'timing.json')
    return generated / 'narration.wav'


def host_source(root, name):
    path = Path(name)
    if path.is_absolute():
        raise ValueError('Host input must be a relative private episode path')
    path = (root / path).resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('Host input must stay inside the episode directory')
    return path


def submit_host(root, mode, live=False, avatar_id=None, character=None, performance=None):
    root, _ = inputs(root)
    ledger = root / 'generated' / 'runway'
    if mode == 'avatar':
        if not avatar_id:
            raise ValueError('Custom Runway avatar ID required')
        audio = narration(root)
        run = lambda is_live: runway_media.submit_avatar(avatar_id, audio, ledger, live=is_live)
    elif mode == 'act_two':
        if not character or not performance:
            raise ValueError('Character plate and filmed performance required')
        a, b = host_source(root, character), host_source(root, performance)
        run = lambda is_live: runway_media.submit_act_two(a, b, ledger, live=is_live)
    else:
        raise ValueError('Host mode must be avatar or act_two')
    preview = run(False)
    record = record_for(root, preview['specification'])
    if record.exists():
        data = json.loads(record.read_text(encoding='utf-8'))
        return {'state': data['state'], 'record': str(record), 'task_id': data.get('task_id')}
    return run(True) if live else preview


def collect_host(root, record_name):
    root, _ = inputs(root)
    record = host_source(root, record_name)
    if record.parent != root / 'generated' / 'runway' or record.suffix != '.json':
        raise ValueError('Use a Runway ledger record from this episode')
    data = json.loads(record.read_text(encoding='utf-8'))
    if data.get('specification', {}).get('kind') not in ('avatar', 'act_two'):
        raise ValueError('Expected an avatar or Act Two record')
    return runway_media.collect(record, root / 'generated' / 'host.mp4')


def render(root, remotion_dir='remotion', video=False):
    root, _ = inputs(root)
    generated_host = root / 'generated' / 'host.mp4'
    plate = root / 'plate.mp4'
    if not plate.is_file() and generated_host.is_file():
        shutil.copyfile(generated_host, plate)
    if not plate.is_file():
        raise ValueError('Supply plate.mp4 or collect the Runway host')
    manifest = production_job.prepare(root, remotion_dir)
    if video:
        import subprocess
        subprocess.run(['npm', 'run', 'render'], cwd=remotion_dir, check=True)
    return {'manifest': str(manifest), 'video': str(Path(remotion_dir) / 'out/reel.mp4')
            if video else None, 'publishable': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'submit-audio', 'collect-audio',
                                             'submit-host', 'collect-host', 'render'))
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--voice-id')
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--mode', choices=('avatar', 'act_two'))
    parser.add_argument('--avatar-id')
    parser.add_argument('--character')
    parser.add_argument('--performance')
    parser.add_argument('--record')
    parser.add_argument('--remotion-dir', default='remotion')
    parser.add_argument('--live', action='store_true', help='Authorize Runway submission')
    parser.add_argument('--render-video', action='store_true')
    args = parser.parse_args()
    if args.command in ('submit-audio', 'collect-audio') and not args.voice_id:
        parser.error('--voice-id required for audio jobs')
    if args.command == 'status':
        result = status(args.input_dir)
    elif args.command == 'submit-audio':
        result = submit_audio(args.input_dir, args.voice_id, args.live, args.workers)
    elif args.command == 'collect-audio':
        result = collect_audio(args.input_dir, args.voice_id)
    elif args.command == 'submit-host':
        result = submit_host(args.input_dir, args.mode, args.live, args.avatar_id,
                             args.character, args.performance)
    elif args.command == 'collect-host':
        if not args.record:
            parser.error('--record required for host collection')
        result = collect_host(args.input_dir, args.record)
    else:
        result = render(args.input_dir, args.remotion_dir, args.render_video)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
