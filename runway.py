"""Runway media adapters for holistic package production.

Owner routing: Runway supplies video AND audio/speech. These adapters build
request plans and dry-run by default. Live submission requires an explicit gate
and credential; ambiguous failures are never auto-retried.

Host on-camera visuals use the operator's Peloton ride plate MP4 (video-to-video),
not a stock Runway avatar preset.

Reference: https://docs.dev.runwayml.com/api/
"""
import base64
import json
import math
import mimetypes
import os
import urllib.error
import urllib.request
from pathlib import Path

from studio import digest
from writer import reserve
from prompts import short as short_prompts

BASE = 'https://api.dev.runwayml.com/v1'
VERSION_HEADER = '2024-11-06'
DEFAULT_HOST_PLATE_PATH = 'media/plates/ride.mp4'

# Catalog of media jobs that can compose a holistic episode package.
CAPABILITIES = {
    'narration_speech': {
        'label': 'Narration speech',
        'role': 'podcast / voiceover audio',
        'method': 'POST',
        'path': '/text_to_speech',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': False,
    },
    'short_video': {
        'label': 'Short vertical video',
        'role': 'TikTok / Reels / Shorts visual bed',
        'method': 'POST',
        'path': '/text_to_video',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': False,
    },
    'host_ride_plate': {
        'label': 'Host ride plate (Peloton)',
        'role': 'on-camera host from your ride.mp4 plate via video-to-video',
        'method': 'POST',
        'path': '/video_to_video',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': True,
    },
    'avatar_presenter': {
        'label': 'Avatar presenter (preset fallback)',
        'role': 'stock Runway preset only — prefer host_ride_plate',
        'method': 'POST',
        'path': '/avatar_videos',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': False,
    },
    'sound_bed': {
        'label': 'Sound bed / effect',
        'role': 'ambience or stinger (labeled non-documentary)',
        'method': 'POST',
        'path': '/sound_effect',
        'provider': 'runway',
        'requires_script': False,
        'requires_host_plate': False,
    },
    'routed_audio': {
        'label': 'Routed speech audio',
        'role': 'model-router speech generation',
        'method': 'POST',
        'path': '/generate/audio',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': False,
    },
    'routed_video': {
        'label': 'Routed video',
        'role': 'model-router video generation',
        'method': 'POST',
        'path': '/generate/video',
        'provider': 'runway',
        'requires_script': True,
        'requires_host_plate': False,
    },
}


def resolve_host_plate(allow_missing=True):
    """Locate the operator's Peloton ride plate.

    Preference order:
    1. RUNWAY_HOST_PLATE_URI — HTTPS / Runway / data URI for live API calls
    2. HOST_PLATE_PATH or media/plates/ride.mp4 — private local file (gitignored)

    Likeness media must not be committed to the public repository.
    """
    uri = (os.environ.get('RUNWAY_HOST_PLATE_URI') or '').strip()
    path = Path(os.environ.get('HOST_PLATE_PATH') or DEFAULT_HOST_PLATE_PATH)
    exists = path.is_file()
    info = {
        'path': str(path),
        'exists': exists,
        'uri': uri or None,
        'source': 'env_uri' if uri else 'local_path',
        'ready_for_live': bool(uri) or exists,
        'note': (
            'Place your Peloton ride.mp4 at media/plates/ride.mp4, or set '
            'HOST_PLATE_PATH / RUNWAY_HOST_PLATE_URI. Do not commit likeness media.'
        ),
    }
    if not allow_missing and not info['ready_for_live']:
        raise ValueError(
            'Host ride plate missing. Copy your Peloton ride MP4 to '
            + str(path) + ' or set RUNWAY_HOST_PLATE_URI.')
    return info


def plate_uri_for_request(plate, live=False):
    """Return a Runway-acceptable URI for the plate video."""
    if plate.get('uri'):
        return plate['uri']
    path = Path(plate['path'])
    if not path.is_file():
        if live:
            raise ValueError('Host ride plate file not found for live Runway call')
        return 'file://' + str(path)
    if not live:
        return 'file://' + str(path.resolve())
    size = path.stat().st_size
    if size > 12_000_000:
        raise ValueError(
            'Ride plate is larger than 12MB. Upload it and set RUNWAY_HOST_PLATE_URI '
            'to an HTTPS or Runway URI before live submission.')
    mime = mimetypes.guess_type(str(path))[0] or 'video/mp4'
    encoded = base64.b64encode(path.read_bytes()).decode('ascii')
    return 'data:' + mime + ';base64,' + encoded


def capabilities():
    """Public catalog for UI and orchestrator selection."""
    plate = resolve_host_plate(allow_missing=True)
    return [
        {
            'id': key,
            **{k: v for k, v in meta.items()},
            **({'host_plate': plate} if meta.get('requires_host_plate') else {}),
        }
        for key, meta in CAPABILITIES.items()
    ]


def script_excerpt(draft, limit=1200):
    """Flatten a produce/writer draft into spoken text for media prompts."""
    if not isinstance(draft, dict):
        return ''
    script = draft.get('script') or draft
    parts = []
    if isinstance(script.get('title'), str):
        parts.append(script['title'])
    for segment in script.get('segments') or []:
        text = segment.get('text')
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    joined = ' '.join(parts).strip()
    return joined[:limit]


def build_request(capability_id, draft, format_name='short', live=False):
    """Build a Runway request plan without contacting the network (unless encoding)."""
    if capability_id not in CAPABILITIES:
        raise ValueError('Unknown media capability: ' + capability_id)
    meta = CAPABILITIES[capability_id]
    spoken = script_excerpt(draft)
    if meta['requires_script'] and not spoken:
        raise ValueError(capability_id + ' needs a reviewed script draft first')
    question = ''
    if isinstance(draft, dict):
        case = draft.get('case') or {}
        question = case.get('question', '')
    plate = None
    body = None
    if capability_id == 'narration_speech':
        text = short_prompts.speech_prompt(spoken) if format_name == 'short' else spoken
        body = {
            'model': 'eleven_multilingual_v2',
            'promptText': text[:2000],
            'voice': {'type': 'runway_preset_voice', 'presetId': 'maya'},
        }
    elif capability_id == 'short_video':
        if format_name == 'short':
            prompt = short_prompts.visual_prompt(question or spoken[:200])
        else:
            prompt = (
                'Documentary-style vertical short. Mystery-first science narration. '
                'No fake interviews. Calm graphics of documents and data. '
                f'Theme: {question or spoken[:200]}'
            )
        body = {
            'model': 'gen4.5',
            'promptText': prompt[:1000],
            'ratio': '720:1280',
            'duration': 10,
        }
    elif capability_id == 'host_ride_plate':
        plate = resolve_host_plate(allow_missing=not live)
        if not plate['ready_for_live'] and live:
            raise ValueError('Host ride plate required for live host_ride_plate job')
        plate_uri = plate_uri_for_request(plate, live=live)
        if format_name == 'short':
            prompt = short_prompts.host_plate_prompt(question or spoken[:220])
        else:
            prompt = (
                'Keep the real host on the Peloton ride plate recognizable. '
                'Documentary mystery-science presenter energy, natural indoor gym lighting, '
                'no face swap to a different person, no fake interview cutaways. '
                f'Editorial theme: {question or spoken[:220]}'
            )
        body = {
            'model': 'seedance2',
            'promptVideo': plate_uri,
            'promptText': prompt[:1000],
            'ratio': '720:1280',
            'duration': 10,
        }
    elif capability_id == 'avatar_presenter':
        body = {
            'model': 'gwm1_avatars',
            'avatar': {'type': 'runway_preset_avatar', 'presetId': 'influencer'},
            'speech': {
                'type': 'text',
                'text': spoken[:2000],
                'voice': {'type': 'runway_preset_voice', 'presetId': 'clara'},
            },
        }
    elif capability_id == 'sound_bed':
        body = {
            'model': 'eleven_text_to_sound_v2',
            'promptText': 'Subtle investigative ambient bed, no melody hook, unlabeled stock ambience',
            'duration': 10,
        }
    elif capability_id == 'routed_audio':
        body = {
            'configId': 'preview-fast',
            'input': {'type': 'speech', 'promptText': spoken[:2000]},
            'dryRun': True,
        }
    elif capability_id == 'routed_video':
        body = {
            'configId': 'preview-fast',
            'input': {
                'type': 'text',
                'promptText': f'Mystery science short visual bed: {question or spoken[:240]}'[:1000],
            },
            'dryRun': True,
        }
    digest_body = body
    if capability_id == 'host_ride_plate' and isinstance(body.get('promptVideo'), str) \
            and body['promptVideo'].startswith('data:'):
        digest_body = dict(body)
        digest_body['promptVideo'] = 'data:video/mp4;base64,[host-plate]'
    plan = {
        'capability_id': capability_id,
        'label': meta['label'],
        'role': meta['role'],
        'provider': 'runway',
        'endpoint': BASE + meta['path'],
        'method': meta['method'],
        'headers_required': ['Authorization', 'X-Runway-Version'],
        'body': body,
        'format': format_name,
        'status': 'planned',
        'publishable': False,
    }
    if plate is not None:
        plan['host_plate'] = {
            'path': plate['path'],
            'exists': plate['exists'],
            'source': plate['source'],
            'uri_kind': (
                'https' if (plate.get('uri') or '').startswith('http')
                else 'data' if isinstance(body.get('promptVideo'), str)
                and body['promptVideo'].startswith('data:')
                else 'file_path'
            ),
        }
    plan['plan_id'] = digest({
        'capability': capability_id, 'body': digest_body, 'format': format_name,
        'plate_path': (plate or {}).get('path'),
    })
    return plan


def plan_package(draft, capability_ids, format_name='short', live=False):
    """Plan multiple Runway jobs for one holistic content package."""
    if not isinstance(capability_ids, list) or not capability_ids:
        raise ValueError('Select at least one media capability')
    unknown = [c for c in capability_ids if c not in CAPABILITIES]
    if unknown:
        raise ValueError('Unknown media capabilities: ' + ', '.join(unknown))
    jobs = [build_request(cid, draft, format_name, live=live) for cid in capability_ids]
    return {
        'provider': 'runway',
        'format': format_name,
        'jobs': jobs,
        'job_count': len(jobs),
        'host_plate': resolve_host_plate(allow_missing=True),
        'status': 'planned',
        'publishable': False,
        'note': 'Plans only. Live Runway calls require RUNWAY_LIVE_ENABLED and credentials.',
    }


def submit(plan, root, live=False, budget=0, max_usd_per_job=0, request=None):
    """Dry-run or live-submit one planned job. Default is dry-run."""
    if plan.get('provider') != 'runway':
        raise ValueError('Not a Runway plan')
    key = plan['plan_id']
    if not live:
        return {
            'mode': 'dry_run',
            'plan_id': key,
            'endpoint': plan['endpoint'],
            'api_calls': 0,
            'status': 'ready_for_configured_live_call',
            'publishable': False,
            'host_plate': plan.get('host_plate'),
        }
    if os.environ.get('RUNWAY_LIVE_ENABLED') != 'true':
        raise ValueError('RUNWAY_LIVE_ENABLED must be true for live media jobs')
    credential = os.environ.get('RUNWAY_API_KEY')
    if not credential:
        raise ValueError('RUNWAY_API_KEY is not configured')
    if not all(math.isfinite(x) and x > 0 for x in [budget, max_usd_per_job]):
        raise ValueError('Budget and per-job reservation must be finite positive numbers')
    if plan.get('capability_id') == 'host_ride_plate':
        rebuilt = build_request(
            'host_ride_plate',
            {'script': {'title': 'x', 'segments': [{'text': plan['body'].get('promptText', 'x')}]}},
            plan.get('format') or 'short',
            live=True,
        )
        body = dict(rebuilt['body'])
        if plan.get('body', {}).get('promptText'):
            body['promptText'] = plan['body']['promptText']
    else:
        body = dict(plan['body'] or {})
    if isinstance(body.get('promptVideo'), str) and body['promptVideo'].startswith('file://'):
        raise ValueError(
            'Live Runway cannot use a local file:// plate. Set RUNWAY_HOST_PLATE_URI '
            'or provide a local ride.mp4 small enough to embed.')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    import sqlite3
    if 'dryRun' in body:
        body['dryRun'] = False
    with sqlite3.connect(root / 'ledger.sqlite') as db:
        reserve(db, key, max_usd_per_job, budget)
        try:
            caller = request or _call_runway
            result = caller(plan['endpoint'], body, credential)
            target = root / key
            target.mkdir(exist_ok=False)
            safe_plan = dict(plan)
            safe_body = dict(body)
            if isinstance(safe_body.get('promptVideo'), str) and safe_body['promptVideo'].startswith('data:'):
                safe_body['promptVideo'] = 'data:video/mp4;base64,[redacted-host-plate]'
            safe_plan['body'] = safe_body
            record = {
                'status': 'review_required',
                'publishable': False,
                'plan': safe_plan,
                'provider_response': result,
                'reserved_usd': max_usd_per_job,
            }
            (target / 'job.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
            db.execute('UPDATE jobs SET state=? WHERE id=?', ('review_required', key))
            db.commit()
            return {'status': 'review_required', 'path': str(target), 'publishable': False}
        except Exception:
            db.execute('UPDATE jobs SET state=? WHERE id=?', ('unknown_or_failed', key))
            db.commit()
            raise


def _call_runway(endpoint, body, credential):
    request = urllib.request.Request(
        endpoint, data=json.dumps(body).encode(),
        headers={
            'Authorization': 'Bearer ' + credential,
            'Content-Type': 'application/json',
            'X-Runway-Version': VERSION_HEADER,
        },
        method='POST',
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError('Response too large')
        return json.loads(raw)
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise RuntimeError('Runway request failed or outcome is unknown; no automatic retry') from None
