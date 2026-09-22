"""Runway media adapters for holistic package production.

Owner routing: Runway supplies video AND audio/speech. These adapters build
request plans and dry-run by default. Live submission requires an explicit gate
and credential; ambiguous failures are never auto-retried.

Reference: https://docs.dev.runwayml.com/api/
"""
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path

from studio import digest
from writer import reserve

BASE = 'https://api.dev.runwayml.com/v1'
VERSION_HEADER = '2024-11-06'

# Catalog of media jobs that can compose a holistic episode package.
CAPABILITIES = {
    'narration_speech': {
        'label': 'Narration speech',
        'role': 'podcast / voiceover audio',
        'method': 'POST',
        'path': '/text_to_speech',
        'provider': 'runway',
        'requires_script': True,
    },
    'short_video': {
        'label': 'Short vertical video',
        'role': 'TikTok / Reels / Shorts visual bed',
        'method': 'POST',
        'path': '/text_to_video',
        'provider': 'runway',
        'requires_script': True,
    },
    'avatar_presenter': {
        'label': 'Avatar presenter',
        'role': 'on-camera host performance from script',
        'method': 'POST',
        'path': '/avatar_videos',
        'provider': 'runway',
        'requires_script': True,
    },
    'sound_bed': {
        'label': 'Sound bed / effect',
        'role': 'ambience or stinger (labeled non-documentary)',
        'method': 'POST',
        'path': '/sound_effect',
        'provider': 'runway',
        'requires_script': False,
    },
    'routed_audio': {
        'label': 'Routed speech audio',
        'role': 'model-router speech generation',
        'method': 'POST',
        'path': '/generate/audio',
        'provider': 'runway',
        'requires_script': True,
    },
    'routed_video': {
        'label': 'Routed video',
        'role': 'model-router video generation',
        'method': 'POST',
        'path': '/generate/video',
        'provider': 'runway',
        'requires_script': True,
    },
}


def capabilities():
    """Public catalog for UI and orchestrator selection."""
    return [
        {'id': key, **{k: v for k, v in meta.items()}}
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


def build_request(capability_id, draft, format_name='short'):
    """Build a Runway request plan without contacting the network."""
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
    body = None
    if capability_id == 'narration_speech':
        body = {
            'model': 'eleven_multilingual_v2',
            'promptText': spoken,
            'voice': {'type': 'runway_preset_voice', 'presetId': 'maya'},
        }
    elif capability_id == 'short_video':
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
    plan['plan_id'] = digest({'capability': capability_id, 'body': body, 'format': format_name})
    return plan


def plan_package(draft, capability_ids, format_name='short'):
    """Plan multiple Runway jobs for one holistic content package."""
    if not isinstance(capability_ids, list) or not capability_ids:
        raise ValueError('Select at least one media capability')
    unknown = [c for c in capability_ids if c not in CAPABILITIES]
    if unknown:
        raise ValueError('Unknown media capabilities: ' + ', '.join(unknown))
    jobs = [build_request(cid, draft, format_name) for cid in capability_ids]
    return {
        'provider': 'runway',
        'format': format_name,
        'jobs': jobs,
        'job_count': len(jobs),
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
        }
    if os.environ.get('RUNWAY_LIVE_ENABLED') != 'true':
        raise ValueError('RUNWAY_LIVE_ENABLED must be true for live media jobs')
    credential = os.environ.get('RUNWAY_API_KEY')
    if not credential:
        raise ValueError('RUNWAY_API_KEY is not configured')
    if not all(math.isfinite(x) and x > 0 for x in [budget, max_usd_per_job]):
        raise ValueError('Budget and per-job reservation must be finite positive numbers')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    import sqlite3
    body = dict(plan['body'] or {})
    # Live routed calls must not keep dryRun:true.
    if 'dryRun' in body:
        body['dryRun'] = False
    with sqlite3.connect(root / 'ledger.sqlite') as db:
        reserve(db, key, max_usd_per_job, budget)
        try:
            caller = request or _call_runway
            result = caller(plan['endpoint'], body, credential)
            target = root / key
            target.mkdir(exist_ok=False)
            record = {
                'status': 'review_required',
                'publishable': False,
                'plan': plan,
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
