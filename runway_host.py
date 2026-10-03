"""Production Aleph plates and Act Two segments using the proven REST adapter.

Prepared media is addressed by SOURCE hash plus recipe, not newly encoded bytes.
The first encoding and its R2 reference survive replacement Actions runners.
Provider journals live both in episode artifacts and at deterministic R2 keys;
reservations are saved before POST, and submitted tasks resume by their IDs.
"""
import hashlib
import json
import math
import subprocess
from pathlib import Path

import media_store
import runway_media
import runway_operation

RECIPE_VERSION = 1


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def missing_object(error):
    """Only an actual absent R2 object permits generation; auth/network errors don't."""
    return str(getattr(error, 'response', {}).get('Error', {}).get('Code')) in {'404', 'NoSuchKey', 'NotFound'}


def restore(key, destination):
    try:
        return media_store.fetch(key, destination)
    except Exception as error:
        if not missing_object(error):
            raise
        return None


def prepared_video(source, seconds, offset, directory, forward_loop=False):
    """Materialize one stable 24fps input, restoring its original bytes on retry."""
    source = Path(source)
    if not math.isfinite(seconds) or not 2 <= seconds <= 30:
        raise ValueError('Prepared video duration must be 2–30 seconds')
    if not math.isfinite(offset) or offset < 0:
        raise ValueError('Prepared video offset must be nonnegative')
    if not forward_loop and offset + seconds > runway_media.duration(source) + .05:
        raise ValueError('Prepared clip extends beyond source footage')
    spec = {'source_sha256': runway_media.digest_file(source), 'seconds': seconds,
            'offset': offset, 'forward_loop': forward_loop, 'fps': 24, 'recipe': RECIPE_VERSION}
    cache = Path(directory) / identity(spec)
    cache.mkdir(parents=True, exist_ok=True)
    manifest = cache / 'prepared.json'
    manifest_key = 'satoshi/host-inputs/' + identity(spec) + '/prepared.json'
    if not manifest.exists():
        restore(manifest_key, manifest)
    target = cache / 'input.mp4'
    if manifest.exists():
        ref = json.loads(manifest.read_text())['media']
        media_store.fetch(ref['key'], target)
        if runway_media.digest_file(target) != ref['sha256']:
            raise ValueError('Prepared media checksum mismatch')
        return target, ref
    # Forward looping preserves pedaling direction. Act Two's automatic shorter
    # character handling must not decide loop direction for this production.
    command = ['ffmpeg', '-nostdin', '-y', '-v', 'error']
    if forward_loop:
        command += ['-stream_loop', '-1']
    command += ['-ss', str(offset), '-i', str(source), '-t', str(seconds),
                '-vf', 'fps=24', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', str(target)]
    subprocess.run(command, check=True, timeout=300)
    if abs(runway_media.duration(target) - seconds) > .1:
        raise ValueError('Prepared video duration drift')
    ref = media_store.persist(target, 'satoshi/host-inputs/' + identity(spec) + '/input.mp4')
    manifest.write_text(json.dumps({'specification': spec, 'media': ref}, indent=2))
    media_store.persist(manifest, manifest_key)
    return target, ref


def operation(kind, body, estimate, artifacts, work):
    """Reuse complete output, poll known tasks, and refuse ambiguous submission retries."""
    request_id = identity({'operation': kind, 'body': body, 'api_version': runway_operation.catalog()['api_version']})[:32]
    jobs = Path(artifacts) / 'runway_host_jobs'
    job = jobs / request_id
    job.mkdir(parents=True, exist_ok=True)
    for name in ('request.json', 'result.json'):
        if not (job / name).exists():
            restore('satoshi/host-journals/' + request_id + '/' + name, job / name)
    def checkpoint():
        # R2 writes must complete before submission, including on the first run.
        for name in ('request.json', 'result.json'):
            if (job / name).exists():
                media_store.persist(job / name, 'satoshi/host-journals/' + request_id + '/' + name)
    request = {'request_id': request_id, 'operation': kind, 'body': body,
               'allow_mutation': True, 'allow_media_spend': True, 'estimated_credits': estimate}
    result = runway_operation.execute(request, checkpoint=checkpoint, job_root=jobs, work_root=work)
    if not result.get('media'):
        raise ValueError('Runway task succeeded without archived media')
    media = result['media'][0]
    target = Path(work) / request_id / 'collected.mp4'
    media_store.fetch(media['key'], target)
    if runway_media.digest_file(target) != media['sha256']:
        raise ValueError('Generated host checksum mismatch')
    return target, {'request_id': request_id, 'task_id': result['response']['id'],
                    'media': media, 'model': body['model']}


def prepare_plate(source, settings, artifacts, work):
    """Make Aleph's setting once. This plate can be reused across episode narration."""
    prompt = str(settings.get('prompt') or '').strip()
    if not prompt:
        raise ValueError('Aleph needs an explicit setting prompt')
    seconds = float(settings.get('seconds', 10))
    offset = float(settings.get('offset_seconds', 0))
    clip, ref = prepared_video(source, seconds, offset, Path(work) / 'prepared')
    body = {'model': 'aleph2', 'videoUri': ref['url'], 'promptText': prompt,
            'outputFormat': 'mp4', 'targetAspectRatio': '9:16'}
    edited, record = operation('post_video_to_video', body, math.ceil(seconds * 28), artifacts, work)
    return edited, record


def perform_segment(plate, driver, settings, artifacts, work):
    """Use a video performance, never audio alone, with explicit expression control."""
    seconds = runway_media.duration(driver)
    if not 3 <= seconds <= 30:
        raise ValueError('Act Two performance must be 3–30 seconds')
    _, character = prepared_video(plate, seconds, 0, Path(work) / 'prepared', forward_loop=True)
    # Restore a fixed encoding of the supplied driver too. The reference remains
    # locked to approved narration; no generative model rewrites its spoken text.
    _, reference = prepared_video(driver, seconds, 0, Path(work) / 'prepared')
    body = {'model': 'act_two', 'character': {'type': 'video', 'uri': character['url']},
            'reference': {'type': 'video', 'uri': reference['url']}, 'ratio': '720:1280',
            'expressionIntensity': settings.get('expression_intensity', 3)}
    return operation('post_character_performance', body, math.ceil(seconds * 5), artifacts, work)
