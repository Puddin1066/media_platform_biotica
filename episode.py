"""Operate one private Satoshi episode without re-submitting paid jobs.

Audio beats can be submitted to Runway concurrently. The host is an independent
plate, an Act Two performance, or a custom avatar created after narration is
assembled. Reviewed source excerpts stay local; Remotion makes the final Reel.
The default commands inspect or dry-run and never publish anything.
"""
import argparse
import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import production_job
import runway_media
from speech_timing import BEATS, assemble
from studio import digest

PREVIEW_NARRATION_TARGET_SECONDS = 29.0
PREVIEW_MIN_BEAT_SECONDS = 1 / 30


def board_only(root):
    root = Path(root).resolve(strict=True)
    board = json.loads((root / 'storyboard.json').read_text(encoding='utf-8'))
    if board.get('status') != 'awaiting_footage' or \
            [c.get('cue_id') for c in board.get('cues', [])] != list(BEATS):
        raise ValueError('Five-beat reviewed storyboard required')
    return root, board


def inputs(root):
    root, board = board_only(root)
    plan = json.loads((root / 'footage-plan.json').read_text(encoding='utf-8'))
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


def _archive_definite_rejection(record):
    """Archive a provider-declared pre-task rejection so one corrected retry is safe.

    Runway ledger state ``rejected_no_task`` is written only for explicit HTTP
    400/422 responses before a task exists. Moving that record out of the
    canonical digest path preserves the rejection evidence while allowing the
    same deterministic specification to be submitted again after code or
    account-side validation has been corrected. Ambiguous states are never
    archived or retried here.
    """
    record = Path(record)
    data = json.loads(record.read_text(encoding='utf-8'))
    if data.get('state') != 'rejected_no_task' or data.get('provider_http_status') not in (400, 422):
        raise ValueError('Only definite Runway pre-task rejections may be retried')
    archive_dir = record.parent / 'rejected-no-task'
    archive_dir.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        archive = archive_dir / f'{record.stem}-{index}.json'
        if not archive.exists():
            record.replace(archive)
            return archive
        index += 1


def _reuse_collected_output(root, record, data, target):
    """Restore a collected task from private local media without provider calls.

    A retry may encounter a durable collected record whose output was written
    under an older local path. Collection must not be repeated against Runway.
    Instead, locate a private cached file, verify its recorded digest, and copy
    it to the current deterministic destination. The ledger's original file
    path is preserved as evidence.
    """
    if data.get('state') != 'collected':
        return None

    root = Path(root).resolve(strict=True)
    record = Path(record)
    target = Path(target).resolve()
    if not target.is_relative_to(root):
        raise ValueError('Collected output destination must stay inside the episode')

    expected = data.get('file_sha256')
    candidates = [target]
    recorded_file = data.get('file')
    if isinstance(recorded_file, str) and recorded_file:
        recorded_path = Path(recorded_file)
        if recorded_path.is_absolute():
            candidates.append(recorded_path)
        else:
            candidates.append(root / recorded_path)
            candidates.append(Path.cwd() / recorded_path)

    # Older implementations used different deterministic output names. Search
    # only private episode media, and only when a recorded digest can prove the
    # file belongs to this completed task.
    if expected:
        for directory in (root / 'audio', root / 'generated'):
            if directory.exists():
                candidates.extend(
                    path for path in directory.rglob('*')
                    if path.is_file() and path.suffix.lower() in
                    {'.mp3', '.wav', '.m4a', '.mp4'}
                )

    seen = set()
    for candidate in candidates:
        try:
            candidate = Path(candidate).resolve(strict=True)
        except (FileNotFoundError, OSError):
            continue
        if candidate in seen or not candidate.is_relative_to(root) or not candidate.is_file():
            continue
        seen.add(candidate)
        actual = runway_media.digest_file(candidate)
        if expected and actual != expected:
            continue

        if not expected:
            # Legacy collected records may predate the digest field. Only a
            # specifically named target or recorded file is accepted in that
            # case; the computed digest is then added without discarding the
            # original collection evidence.
            expected = actual
            data['file_sha256'] = actual
            runway_media.update(record, data)

        if candidate != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            part = target.with_suffix(target.suffix + '.recovery.part')
            try:
                shutil.copyfile(candidate, part)
                if runway_media.digest_file(part) != expected:
                    raise RuntimeError('Cached Runway output failed integrity verification')
                part.replace(target)
            finally:
                part.unlink(missing_ok=True)

        return {'state': 'collected', 'task_id': data.get('task_id'),
                'file': str(target)}

    raise RuntimeError(
        'Collected Runway task has no intact private local output; '
        'the task record was preserved and was not collected twice')


def status(root):
    root, board = board_only(root)
    plan_ready = False
    try:
        inputs(root)
        plan_ready = True
    except (FileNotFoundError, ValueError, KeyError):
        pass
    return {'episode': str(root), 'script_sha256': board['script_sha256'],
            'audio': {beat: ('ready' if beat_file(root, beat) else 'missing') for beat in BEATS},
            'host': 'ready' if (root / 'plate.mp4').is_file() or
                    (root / 'generated' / 'host.mp4').is_file() else 'missing',
            'footage': 'six reviewed local sources' if plan_ready else 'needs_reviewed_plan',
            'render': 'ready' if all(beat_file(root, b) for b in BEATS) and
                      plan_ready and
                      ((root / 'plate.mp4').is_file() or
                       (root / 'generated' / 'host.mp4').is_file()) else 'needs_assets',
            'publishable': False}


def submit_audio(root, voice_id, live=False, workers=5):
    """Start only absent beats; ledger identity prevents duplicate paid jobs.

    ``reserved_unknown`` remains non-retryable because the provider outcome is
    ambiguous. A definite 400/422 ``rejected_no_task`` record may be archived
    and retried when live execution is explicitly authorized because no provider
    task existed for that rejected request.
    """
    root, board = board_only(root)
    if not 1 <= workers <= 5:
        raise ValueError('Use 1–5 simultaneous Runway speech jobs')

    def one(beat):
        if beat_file(root, beat):
            return beat, {'state': 'audio_ready'}
        preview = runway_media.submit_tts(board, beat, voice_id, root / 'generated' / 'runway')
        path = record_for(root, preview['specification'])
        if path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            if live and record.get('state') == 'rejected_no_task':
                _archive_definite_rejection(path)
                return beat, runway_media.submit_tts(
                    board, beat, voice_id, root / 'generated' / 'runway', live=True)
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
    root, board = board_only(root)
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
        target = root / 'audio' / (beat + '.mp3')
        if data.get('state') == 'submitted':
            result[beat] = runway_media.collect(record, target)['state']
        elif data.get('state') == 'collected':
            _reuse_collected_output(root, record, data, target)
            result[beat] = 'audio_ready'
        else:
            result[beat] = data.get('state', 'reserved_unknown')
    return result


def _atempo_filter(rate):
    """Build an ffmpeg-compatible tempo chain without changing pitch."""
    if rate <= 0:
        raise ValueError('Audio tempo must be positive')
    values = []
    remaining = rate
    while remaining > 2:
        values.append(2.0)
        remaining /= 2
    while remaining < 0.5:
        values.append(0.5)
        remaining /= 0.5
    values.append(remaining)
    return ','.join(f'atempo={value:.10g}' for value in values)


def _fit_unreviewed_preview_audio(root, files):
    """Create replayable local derivatives when preview speech nears 30s.

    Original provider audio remains untouched. The transformation is restricted
    to explicitly unreviewed previews and is recorded with source/output hashes
    so retries can reuse it without another provider call. A one-second margin
    is retained because speech timing converts each beat independently to whole
    30-fps frames; audio below 30 seconds can otherwise round beyond 900 frames.
    """
    durations = {beat: runway_media.duration(path) for beat, path in files.items()}
    if any(value <= 0 for value in durations.values()):
        raise ValueError('Unreviewed preview contains an empty speech beat')
    total = sum(durations.values())
    if total <= PREVIEW_NARRATION_TARGET_SECONDS and \
            all(value >= PREVIEW_MIN_BEAT_SECONDS for value in durations.values()):
        return files

    tempo = total / PREVIEW_NARRATION_TARGET_SECONDS
    if min(durations.values()) / tempo < PREVIEW_MIN_BEAT_SECONDS:
        raise ValueError('Preview narration cannot fit 30 seconds without losing a speech beat')

    generated = root / 'generated'
    fitted_dir = generated / 'preview-audio-fit'
    metadata_path = generated / 'preview-audio-fit.json'
    source_hashes = {beat: runway_media.digest_file(path) for beat, path in files.items()}

    try:
        metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        metadata = None
    if metadata and metadata.get('source_sha256') == source_hashes and \
            metadata.get('target_seconds') == PREVIEW_NARRATION_TARGET_SECONDS:
        cached = {}
        valid = True
        for beat in BEATS:
            entry = metadata.get('files', {}).get(beat, {})
            candidate = root / entry.get('output', '')
            try:
                resolved = candidate.resolve(strict=True)
            except (FileNotFoundError, OSError):
                valid = False
                break
            if not resolved.is_relative_to(root) or \
                    runway_media.digest_file(resolved) != entry.get('output_sha256'):
                valid = False
                break
            cached[beat] = resolved
        if valid:
            cached_durations = [runway_media.duration(path) for path in cached.values()]
            if sum(cached_durations) <= 30 and \
                    all(value >= PREVIEW_MIN_BEAT_SECONDS for value in cached_durations):
                return cached

    fitted_dir.mkdir(parents=True, exist_ok=True)
    fitted = {}
    entries = {}
    audio_filter = _atempo_filter(tempo)
    for beat in BEATS:
        source = files[beat]
        target = fitted_dir / (beat + '.wav')
        part = fitted_dir / (beat + '.part.wav')
        part.unlink(missing_ok=True)
        proc = subprocess.run([
            'ffmpeg', '-nostdin', '-loglevel', 'error', '-y',
            '-i', str(source), '-vn', '-filter:a', audio_filter,
            '-acodec', 'pcm_s16le', str(part),
        ], text=True, capture_output=True)
        if proc.returncode != 0:
            part.unlink(missing_ok=True)
            raise RuntimeError(
                'Could not fit unreviewed preview narration locally: ' +
                (proc.stderr or f'ffmpeg exit {proc.returncode}').strip())
        part.replace(target)
        fitted[beat] = target
        entries[beat] = {
            'source': str(source.relative_to(root)),
            'source_duration_seconds': durations[beat],
            'output': str(target.relative_to(root)),
            'output_sha256': runway_media.digest_file(target),
        }

    fitted_durations = {beat: runway_media.duration(path)
                        for beat, path in fitted.items()}
    if sum(fitted_durations.values()) > 30 or \
            any(value < PREVIEW_MIN_BEAT_SECONDS for value in fitted_durations.values()):
        raise RuntimeError('Local preview narration fit did not satisfy the 30-second timing gate')

    metadata = {
        'schema_version': 1,
        'purpose': 'UNREVIEWED_PREVIEW_ONLY',
        'source_sha256': source_hashes,
        'source_total_seconds': total,
        'target_seconds': PREVIEW_NARRATION_TARGET_SECONDS,
        'tempo_multiplier': tempo,
        'output_total_seconds': sum(fitted_durations.values()),
        'files': entries,
        'publishable': False,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return fitted


def narration(root):
    root, board = board_only(root)
    files = {beat: beat_file(root, beat) for beat in BEATS}
    if any(path is None for path in files.values()):
        raise ValueError('Collect or record all five audio beats before assembling narration')
    if board.get('review_status') == 'unreviewed_web_preview':
        files = _fit_unreviewed_preview_audio(root, files)
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
    root, _ = board_only(root)
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
    root, _ = board_only(root)
    record = host_source(root, record_name)
    if record.parent != root / 'generated' / 'runway' or record.suffix != '.json':
        raise ValueError('Use a Runway ledger record from this episode')
    data = json.loads(record.read_text(encoding='utf-8'))
    if data.get('specification', {}).get('kind') not in ('avatar', 'act_two'):
        raise ValueError('Expected an avatar or Act Two record')
    target = root / 'generated' / 'host.mp4'
    if data.get('state') == 'collected':
        return _reuse_collected_output(root, record, data, target)
    if data.get('state') != 'submitted':
        return {'state': data.get('state', 'reserved_unknown'),
                'task_id': data.get('task_id'), 'file': data.get('file')}
    return runway_media.collect(record, target)


def submit_visual(root, cue, prompt, live=False):
    """Generate a proposed illustration while footage selection continues."""
    root, board = board_only(root)
    ledger = root / 'generated' / 'runway'
    preview = runway_media.submit_visual(board, cue, prompt, ledger)
    record = record_for(root, preview['specification'])
    if record.exists():
        data = json.loads(record.read_text(encoding='utf-8'))
        if live and data.get('state') == 'rejected_no_task':
            _archive_definite_rejection(record)
            return runway_media.submit_visual(board, cue, prompt, ledger, live=True)
        return {'state': data['state'], 'record': str(record), 'task_id': data.get('task_id')}
    return runway_media.submit_visual(board, cue, prompt, ledger, live=True) if live else preview


def collect_visual(root, record_name):
    """Collect media as an unapproved candidate, never as a factual receipt."""
    root, board = board_only(root)
    record = host_source(root, record_name)
    if record.parent != root / 'generated' / 'runway' or record.suffix != '.json':
        raise ValueError('Use a Runway ledger record from this episode')
    data = json.loads(record.read_text(encoding='utf-8'))
    spec = data.get('specification', {})
    if spec.get('kind') != 'visual' or spec.get('script_sha256') != board['script_sha256']:
        raise ValueError('Visual task must match this reviewed storyboard')
    cue = spec['cue_id']
    stem = 'visual-' + cue + '-' + record.stem[:12]
    target = root / 'generated' / (stem + '.mp4')
    if data.get('state') == 'collected':
        result = _reuse_collected_output(root, record, data, target)
    elif data.get('state') == 'submitted':
        result = runway_media.collect(record, target)
    else:
        return {'state': data.get('state', 'reserved_unknown'),
                'task_id': data.get('task_id'), 'file': data.get('file')}
    if result['state'] == 'collected':
        candidate = {'id': 'runway:' + runway_media.digest_file(target),
                     'provider': 'runway', 'cue_id': cue,
                     'media_source': str(target.relative_to(root)),
                     'rights_status': 'review_required',
                     'visual_type': 'illustration', 'prompt': spec['prompt'],
                     'note': 'Generated illustration; editor must inspect and approve any use.'}
        (root / 'generated' / (stem + '.json')).write_text(
            json.dumps({'cue_id': cue, 'candidates': [candidate]}, indent=2) + '\n',
            encoding='utf-8')
        result['candidate'] = candidate
    return result


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
        subprocess.run(['npm', 'run', 'render'], cwd=remotion_dir, check=True)
    return {'manifest': str(manifest), 'video': str(Path(remotion_dir) / 'out/reel.mp4')
            if video else None, 'publishable': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('status', 'submit-audio', 'collect-audio',
                                             'submit-host', 'collect-host',
                                             'submit-visual', 'collect-visual', 'render'))
    parser.add_argument('--input-dir', required=True)
    parser.add_argument('--voice-id')
    parser.add_argument('--workers', type=int, default=5)
    parser.add_argument('--mode', choices=('avatar', 'act_two'))
    parser.add_argument('--avatar-id')
    parser.add_argument('--character')
    parser.add_argument('--performance')
    parser.add_argument('--record')
    parser.add_argument('--cue', choices=BEATS)
    parser.add_argument('--prompt')
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
    elif args.command == 'submit-visual':
        if not args.cue or not args.prompt:
            parser.error('--cue and --prompt required for visual generation')
        result = submit_visual(args.input_dir, args.cue, args.prompt, args.live)
    elif args.command == 'collect-visual':
        if not args.record:
            parser.error('--record required for visual collection')
        result = collect_visual(args.input_dir, args.record)
    else:
        result = render(args.input_dir, args.remotion_dir, args.render_video)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
