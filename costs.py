"""Operator-facing cost estimates for pipeline stages.

Estimates use configurable rates. They are planning aids, not provider invoices.
Actual USD is derived from returned usage when available; otherwise recorded as
unavailable. Dry-runs always record actual as zero spend.
"""
import math
import os

# Default rates — operators should verify against current provider pricing.
DEFAULT_RATES = {
    'openai_input_usd_per_million': float(os.environ.get('OPENAI_INPUT_USD_PER_MILLION', '0.15')),
    'openai_output_usd_per_million': float(os.environ.get('OPENAI_OUTPUT_USD_PER_MILLION', '0.60')),
    'openai_web_search_usd_per_call': float(os.environ.get('OPENAI_WEB_SEARCH_USD_PER_CALL', '0.025')),
    # Rough planning defaults per Runway capability (not official quotes).
    'runway_narration_speech_usd': float(os.environ.get('RUNWAY_NARRATION_SPEECH_USD', '0.08')),
    'runway_short_video_usd': float(os.environ.get('RUNWAY_SHORT_VIDEO_USD', '0.50')),
    'runway_avatar_presenter_usd': float(os.environ.get('RUNWAY_AVATAR_PRESENTER_USD', '0.80')),
    'runway_sound_bed_usd': float(os.environ.get('RUNWAY_SOUND_BED_USD', '0.05')),
    'runway_routed_audio_usd': float(os.environ.get('RUNWAY_ROUTED_AUDIO_USD', '0.10')),
    'runway_routed_video_usd': float(os.environ.get('RUNWAY_ROUTED_VIDEO_USD', '0.50')),
}

RUNWAY_RATE_KEYS = {
    'narration_speech': 'runway_narration_speech_usd',
    'short_video': 'runway_short_video_usd',
    'avatar_presenter': 'runway_avatar_presenter_usd',
    'sound_bed': 'runway_sound_bed_usd',
    'routed_audio': 'runway_routed_audio_usd',
    'routed_video': 'runway_routed_video_usd',
}


def merge_rates(overrides=None):
    rates = dict(DEFAULT_RATES)
    if overrides:
        for key, value in overrides.items():
            if key in rates and value is not None:
                try:
                    num = float(value)
                except (TypeError, ValueError):
                    continue
                if math.isfinite(num) and num >= 0:
                    rates[key] = num
    return rates


def round_usd(value):
    return round(float(value), 6)


def _round_usd(value):
    return round_usd(value)


def _openai_token_usd(input_tokens, output_tokens, rates):
    return (
        (input_tokens / 1_000_000.0) * rates['openai_input_usd_per_million']
        + (output_tokens / 1_000_000.0) * rates['openai_output_usd_per_million']
    )


def estimate_research(plan, max_tool_calls=4, rates=None):
    """Bounded estimate for hypothesis web-search memos."""
    rates = merge_rates(rates)
    searches = max(0, len(plan or []))
    tool_calls = searches * max(1, int(max_tool_calls))
    # Rough prompt+completion envelope per search request.
    input_tokens = searches * 1800
    output_tokens = searches * 2200
    token_usd = _openai_token_usd(input_tokens, output_tokens, rates)
    tool_usd = tool_calls * rates['openai_web_search_usd_per_call']
    return {
        'provider': 'openai',
        'unit': 'tokens+tool_calls',
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tool_calls': tool_calls,
        'searches': searches,
        'usd': _round_usd(token_usd + tool_usd),
        'components': {
            'token_usd': _round_usd(token_usd),
            'web_search_tool_usd': _round_usd(tool_usd),
        },
        'rates_used': {
            'openai_input_usd_per_million': rates['openai_input_usd_per_million'],
            'openai_output_usd_per_million': rates['openai_output_usd_per_million'],
            'openai_web_search_usd_per_call': rates['openai_web_search_usd_per_call'],
        },
        'note': 'Estimate only. Verify current OpenAI model and web_search tool pricing.',
    }


def estimate_writing(formats, plan, max_tool_calls=6, rates=None):
    """Estimate produce.py web-search drafting across selected formats."""
    rates = merge_rates(rates)
    formats = list(formats or [])
    searches = max(1, len(plan or []))
    # One Responses call per format; tool calls shared envelope.
    calls = max(1, len(formats))
    tool_calls = calls * max(1, int(max_tool_calls))
    input_tokens = calls * (2200 + searches * 200)
    output_tokens = calls * 2500
    token_usd = _openai_token_usd(input_tokens, output_tokens, rates)
    tool_usd = tool_calls * rates['openai_web_search_usd_per_call']
    return {
        'provider': 'openai',
        'unit': 'tokens+tool_calls',
        'formats': formats,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tool_calls': tool_calls,
        'usd': _round_usd(token_usd + tool_usd),
        'components': {
            'token_usd': _round_usd(token_usd),
            'web_search_tool_usd': _round_usd(tool_usd),
        },
        'rates_used': {
            'openai_input_usd_per_million': rates['openai_input_usd_per_million'],
            'openai_output_usd_per_million': rates['openai_output_usd_per_million'],
            'openai_web_search_usd_per_call': rates['openai_web_search_usd_per_call'],
        },
        'note': 'Estimate only. Live produce uses web_search; prices must be verified.',
    }


def estimate_media(formats, media_targets, rates=None):
    """Estimate Runway package cost (credits approximated as USD planning defaults)."""
    rates = merge_rates(rates)
    formats = list(formats or [])
    media_targets = list(media_targets or [])
    jobs = []
    total = 0.0
    for fmt in formats:
        for mid in media_targets:
            key = RUNWAY_RATE_KEYS.get(mid)
            usd = rates.get(key, 0.0) if key else 0.0
            jobs.append({'format': fmt, 'capability_id': mid, 'usd': _round_usd(usd)})
            total += usd
    return {
        'provider': 'runway',
        'unit': 'jobs',
        'job_count': len(jobs),
        'input_tokens': 0,
        'output_tokens': 0,
        'tool_calls': 0,
        'jobs': jobs,
        'usd': _round_usd(total),
        'rates_used': {k: rates[k] for k in RUNWAY_RATE_KEYS.values()},
        'note': 'Runway billing is credit/model based; these USD figures are operator planning defaults, not invoices.',
    }


def actual_zero(provider='none'):
    return {
        'provider': provider,
        'input_tokens': 0,
        'output_tokens': 0,
        'tool_calls': 0,
        'usd': 0.0,
        'source': 'dry_run_zero',
        'note': 'Dry-run made no paid provider calls.',
    }


def actual_from_openai_usage(usage, tool_calls=0, rates=None):
    """Map Responses usage into tokens + estimated USD."""
    rates = merge_rates(rates)
    if not isinstance(usage, dict):
        return {
            'provider': 'openai',
            'input_tokens': None,
            'output_tokens': None,
            'tool_calls': tool_calls,
            'usd': None,
            'source': 'unavailable',
            'note': 'Provider usage missing; cannot compute actual token USD.',
        }
    input_tokens = usage.get('input_tokens', usage.get('prompt_tokens'))
    output_tokens = usage.get('output_tokens', usage.get('completion_tokens'))
    try:
        input_tokens = int(input_tokens) if input_tokens is not None else None
        output_tokens = int(output_tokens) if output_tokens is not None else None
    except (TypeError, ValueError):
        input_tokens = output_tokens = None
    usd = None
    source = 'unavailable'
    if input_tokens is not None and output_tokens is not None:
        token_usd = _openai_token_usd(input_tokens, output_tokens, rates)
        tool_usd = max(0, int(tool_calls)) * rates['openai_web_search_usd_per_call']
        usd = _round_usd(token_usd + tool_usd)
        source = 'provider_usage_plus_tool_rate'
    return {
        'provider': 'openai',
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'tool_calls': tool_calls,
        'usd': usd,
        'raw_usage': usage,
        'source': source,
        'note': 'Token USD uses operator rates; tool USD uses configured per-call rate.',
    }


def actual_from_runway_jobs(job_results, rates=None):
    """Runway rarely returns USD; keep estimate linkage and mark source."""
    rates = merge_rates(rates)
    if not job_results:
        return actual_zero('runway')
    return {
        'provider': 'runway',
        'input_tokens': 0,
        'output_tokens': 0,
        'tool_calls': 0,
        'job_count': len(job_results),
        'usd': None,
        'source': 'provider_does_not_return_usd',
        'note': 'Inspect Runway dashboard/credits for actual spend; planning USD remains on the estimate.',
    }


def cost_block(estimate, actual):
    return {
        'estimate': estimate,
        'actual': actual,
        'delta_usd': (
            None if estimate.get('usd') is None or actual.get('usd') is None
            else _round_usd(actual['usd'] - estimate['usd'])
        ),
    }


def rollup(run):
    """Sum stage costs for UI totals."""
    est_usd = 0.0
    act_usd = 0.0
    act_known = True
    est_in = est_out = act_in = act_out = 0
    rows = []
    for name in ('theme', 'research', 'writing', 'media', 'review'):
        stage = (run.get('stages') or {}).get(name) or {}
        cost = stage.get('cost')
        if not cost:
            continue
        est = cost.get('estimate') or {}
        act = cost.get('actual') or {}
        if isinstance(est.get('usd'), (int, float)):
            est_usd += est['usd']
        if isinstance(est.get('input_tokens'), int):
            est_in += est['input_tokens']
        if isinstance(est.get('output_tokens'), int):
            est_out += est['output_tokens']
        if isinstance(act.get('usd'), (int, float)):
            act_usd += act['usd']
        else:
            if stage.get('status') not in ('ready', 'blocked', 'skipped') and name != 'theme':
                # Live without usage still unknown.
                if (act.get('source') or '') not in ('dry_run_zero',):
                    act_known = act_known and act.get('usd') == 0
                if act.get('usd') is None and act.get('source') not in ('dry_run_zero', None):
                    act_known = False
        if isinstance(act.get('input_tokens'), int):
            act_in += act['input_tokens']
        if isinstance(act.get('output_tokens'), int):
            act_out += act['output_tokens']
        rows.append({
            'stage': name,
            'status': stage.get('status'),
            'estimate_usd': est.get('usd'),
            'actual_usd': act.get('usd'),
            'estimate_input_tokens': est.get('input_tokens'),
            'estimate_output_tokens': est.get('output_tokens'),
            'actual_input_tokens': act.get('input_tokens'),
            'actual_output_tokens': act.get('output_tokens'),
        })
    return {
        'stages': rows,
        'estimate_usd_total': _round_usd(est_usd),
        'actual_usd_total': _round_usd(act_usd) if act_known else None,
        'estimate_input_tokens': est_in,
        'estimate_output_tokens': est_out,
        'actual_input_tokens': act_in,
        'actual_output_tokens': act_out,
        'currency': 'USD',
        'note': 'Totals use operator rates. Actual may be null when provider omits billing fields.',
    }


def preview_next(run, rates=None, max_tool_calls_research=4, max_tool_calls_writing=6):
    """Estimate the next ready stage without executing it."""
    rates = merge_rates(rates)
    stages = run.get('stages') or {}
    if stages.get('research', {}).get('status') == 'ready':
        est = estimate_research(run.get('research_plan'), max_tool_calls_research, rates)
        return {'stage': 'research', 'estimate': est}
    if stages.get('writing', {}).get('status') == 'ready':
        est = estimate_writing(run.get('formats'), run.get('research_plan'),
                               max_tool_calls_writing, rates)
        return {'stage': 'writing', 'estimate': est}
    if stages.get('media', {}).get('status') == 'ready':
        est = estimate_media(run.get('formats'), run.get('media_targets'), rates)
        return {'stage': 'media', 'estimate': est}
    if stages.get('review', {}).get('status') == 'ready' or run.get('stage') == 'review':
        return {
            'stage': 'review',
            'estimate': {
                'provider': 'none', 'usd': 0.0, 'input_tokens': 0, 'output_tokens': 0,
                'note': 'Review gate has no model cost.',
            },
        }
    return {'stage': None, 'estimate': None}
