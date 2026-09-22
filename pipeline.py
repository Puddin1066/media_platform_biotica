"""Step-wise Inquiry Studio pipeline orchestrator.

Chains: theme/hypothesis → research → writing → Runway media planning/production.
Each stage is independently runnable, dry-run by default, and never publishable
without human review. The UI and CLI both call these functions.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import produce
import runway
import web_research
from studio import digest, validate

STAGES = ['theme', 'research', 'writing', 'media', 'review']
DEFAULT_CASE = 'cases/mens-health.json'
DEFAULT_PLAN = 'cases/research-plan.json'
WRITING_FORMATS = ['short', 'podcast', 'newsletter', 'treatment']


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _load_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def _write_run(root, run):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / (run['run_id'] + '.json')
    path.write_text(json.dumps(run, indent=2) + '\n', encoding='utf-8')
    return path


def load_run(root, run_id):
    path = Path(root) / (run_id + '.json')
    if not path.exists():
        raise FileNotFoundError('Unknown pipeline run')
    return json.loads(path.read_text(encoding='utf-8'))


def list_runs(root):
    root = Path(root)
    if not root.exists():
        return []
    runs = []
    for path in sorted(root.glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        runs.append({
            'run_id': data.get('run_id'),
            'theme': data.get('theme'),
            'stage': data.get('stage'),
            'updated_at': data.get('updated_at'),
            'publishable': False,
        })
    return runs


def bootstrap(case_path=DEFAULT_CASE):
    """Data the UI needs before creating a run."""
    case = validate(_load_json(case_path))
    return {
        'case_path': case_path,
        'theme': case['question'],
        'case_id': case['id'],
        'hypotheses': case['hypotheses'],
        'writing_formats': WRITING_FORMATS,
        'media_capabilities': runway.capabilities(),
        'stages': STAGES,
        'publishable': False,
        'note': 'Dry-run is default. Live OpenAI/Runway calls need explicit gates and credentials.',
    }


def start(case_path=DEFAULT_CASE, hypothesis_ids=None, formats=None,
          media_targets=None, root='outputs/pipeline', plan_path=DEFAULT_PLAN):
    """Create a pipeline run from a men's-health (or other) theme case."""
    case = validate(_load_json(case_path))
    available = {h['id'] for h in case['hypotheses']}
    selected = list(hypothesis_ids) if hypothesis_ids else [h['id'] for h in case['hypotheses']]
    if not selected or not set(selected) <= available:
        raise ValueError('Select known hypothesis IDs from the case')
    formats = list(formats) if formats else ['short']
    if not formats or any(f not in WRITING_FORMATS for f in formats):
        raise ValueError('Choose writing formats from: ' + ', '.join(WRITING_FORMATS))
    media_targets = list(media_targets) if media_targets else [
        'narration_speech', 'short_video', 'avatar_presenter']
    for mid in media_targets:
        if mid not in runway.CAPABILITIES:
            raise ValueError('Unknown media target: ' + mid)
    plan = _load_json(plan_path)
    plan = [entry for entry in plan if entry.get('hypothesis_id') in selected]
    if not plan:
        # Fall back to produce-style cues for selected hypotheses.
        plan = [entry for entry in produce.default_plan(case)
                if entry['hypothesis_id'] in selected]
    run_id = digest({
        'case': digest(case), 'hypotheses': selected, 'formats': formats,
        'media': media_targets, 'started': _utc(),
    })[:16]
    run = {
        'version': 1,
        'run_id': run_id,
        'created_at': _utc(),
        'updated_at': _utc(),
        'case_path': case_path,
        'plan_path': plan_path,
        'theme': case['question'],
        'case_id': case['id'],
        'hypothesis_ids': selected,
        'formats': formats,
        'media_targets': media_targets,
        'research_plan': plan,
        'stage': 'theme',
        'stages': {
            'theme': {
                'status': 'done',
                'completed_at': _utc(),
                'summary': f"Theme locked with {len(selected)} hypotheses; formats={formats}",
            },
            'research': {'status': 'ready'},
            'writing': {'status': 'blocked', 'reason': 'Complete or skip research first'},
            'media': {'status': 'blocked', 'reason': 'Complete writing first'},
            'review': {'status': 'blocked', 'reason': 'Complete prior stages first'},
        },
        'artifacts': {},
        'publishable': False,
        'status': 'active',
    }
    path = _write_run(root, run)
    run['path'] = str(path)
    return run


def _unlock(run, stage, status='ready'):
    run['stages'][stage] = {'status': status}
    if 'reason' in run['stages'][stage]:
        del run['stages'][stage]['reason']


def run_research(run, root='outputs/pipeline', live=False, budget=0,
                 max_usd_per_search=0, max_tool_calls=4, request=None):
    """Stage 2: web-search research for selected hypotheses."""
    if run['stages']['theme']['status'] != 'done':
        raise ValueError('Lock the theme before research')
    case = validate(_load_json(run['case_path']))
    plan = run['research_plan']
    kwargs = dict(live=live, budget=budget, max_usd_per_search=max_usd_per_search,
                  max_tool_calls=max_tool_calls)
    if request is not None:
        kwargs['request'] = request
    result = web_research.run(
        case, plan, 'gpt-4o-mini', Path(root) / run['run_id'] / 'research', **kwargs)
    run['stages']['research'] = {
        'status': 'done' if not live else 'review_required',
        'completed_at': _utc(),
        'mode': result.get('mode', 'live'),
        'result': result,
        'summary': f"Research {'dry-run' if not live else 'live'} for {result.get('planned_searches', result.get('searches', 0))} queries",
    }
    run['artifacts']['research'] = result
    _unlock(run, 'writing')
    run['stage'] = 'writing'
    run['updated_at'] = _utc()
    _write_run(root, run)
    return run


def run_writing(run, root='outputs/pipeline', live=False, budget=0,
                max_usd_per_run=0, max_tool_calls=6, request=None):
    """Stage 3: web-search-primary narration for each selected format."""
    if run['stages']['research']['status'] not in ('done', 'review_required', 'skipped'):
        raise ValueError('Run or skip research before writing')
    case = validate(_load_json(run['case_path']))
    plan = run['research_plan']
    drafts = {}
    for fmt in run['formats']:
        kwargs = dict(live=live, budget=budget, max_usd_per_run=max_usd_per_run,
                      max_tool_calls=max_tool_calls)
        if request is not None:
            kwargs['request'] = request
        drafts[fmt] = produce.run(
            case, plan, fmt, 'gpt-4o-mini',
            Path(root) / run['run_id'] / 'writing' / fmt, **kwargs)
    run['stages']['writing'] = {
        'status': 'done' if not live else 'review_required',
        'completed_at': _utc(),
        'mode': 'dry_run' if not live else 'live',
        'result': drafts,
        'summary': f"Writing {'dry-run' if not live else 'live'} for formats {run['formats']}",
    }
    run['artifacts']['writing'] = drafts
    _unlock(run, 'media')
    run['stage'] = 'media'
    run['updated_at'] = _utc()
    _write_run(root, run)
    return run


def run_media(run, root='outputs/pipeline', live=False, budget=0, max_usd_per_job=0,
              draft_override=None):
    """Stage 4: plan (and optionally submit) Runway jobs for holistic media."""
    if run['stages']['writing']['status'] not in ('done', 'review_required', 'skipped'):
        raise ValueError('Run writing before media production')
    # Prefer an explicit draft; otherwise build a placeholder from case theme
    # so dry-run media planning works before live OpenAI writing.
    draft = draft_override
    if draft is None:
        case = validate(_load_json(run['case_path']))
        writing = run['artifacts'].get('writing') or {}
        # If a live produce draft path exists, load it; else synthesize planning text.
        draft = {
            'case': case,
            'script': {
                'title': 'Planning draft — ' + case['question'][:80],
                'open_question': case['question'],
                'segments': [
                    {
                        'beat': beat,
                        'text': f'[{beat}] Placeholder awaiting live web-search draft for: {case["question"]}',
                        'source_urls': ['https://example.org/placeholder'],
                        'production_note': 'Planning only; replace after produce.py live draft',
                    }
                    for beat in produce.BEATS
                ],
            },
            'status': 'planning_placeholder',
            'writing_modes': {fmt: (writing.get(fmt) or {}).get('mode') for fmt in run['formats']},
        }
    packages = {}
    submissions = {}
    for fmt in run['formats']:
        package = runway.plan_package(draft, run['media_targets'], fmt)
        packages[fmt] = package
        if live:
            submissions[fmt] = []
            for job in package['jobs']:
                submissions[fmt].append(runway.submit(
                    job, Path(root) / run['run_id'] / 'media' / fmt,
                    live=True, budget=budget, max_usd_per_job=max_usd_per_job))
    run['stages']['media'] = {
        'status': 'done' if not live else 'review_required',
        'completed_at': _utc(),
        'mode': 'dry_run' if not live else 'live',
        'result': {'packages': packages, 'submissions': submissions},
        'summary': (
            f"Planned {sum(p['job_count'] for p in packages.values())} Runway jobs "
            f"across {len(packages)} formats"
        ),
    }
    run['artifacts']['media'] = packages
    _unlock(run, 'review')
    run['stage'] = 'review'
    run['updated_at'] = _utc()
    _write_run(root, run)
    return run


def skip_stage(run, stage, root='outputs/pipeline', reason='Operator skipped'):
    """Allow directed progression without executing a stage."""
    if stage not in ('research', 'writing'):
        raise ValueError('Only research or writing can be skipped')
    run['stages'][stage] = {
        'status': 'skipped',
        'completed_at': _utc(),
        'summary': reason,
    }
    order = STAGES
    idx = order.index(stage)
    nxt = order[idx + 1]
    _unlock(run, nxt)
    run['stage'] = nxt
    run['updated_at'] = _utc()
    _write_run(root, run)
    return run


def review_summary(run):
    """Final gate view — still never auto-publishes."""
    return {
        'run_id': run['run_id'],
        'theme': run['theme'],
        'stage': run['stage'],
        'stage_statuses': {name: run['stages'][name].get('status') for name in STAGES},
        'formats': list(run['formats']),
        'media_targets': list(run['media_targets']),
        'artifacts': {
            'research': bool(run['artifacts'].get('research')),
            'writing': bool(run['artifacts'].get('writing')),
            'media': bool(run['artifacts'].get('media')),
        },
        'publishable': False,
        'status': 'review_required',
        'blockers': [
            'Human factual review required',
            'Rights clearance required',
            'No automatic publication',
            'Live provider outputs remain review_required',
        ],
    }


def advance(run, root='outputs/pipeline', live=False, **kwargs):
    """Execute the next ready stage based on stage status flags."""
    status = {name: run['stages'][name]['status'] for name in STAGES}
    if status['research'] == 'ready':
        return run_research(run, root=root, live=live, **{
            k: kwargs[k] for k in ('budget', 'max_usd_per_search', 'max_tool_calls', 'request')
            if k in kwargs})
    if status['writing'] == 'ready':
        return run_writing(run, root=root, live=live, **{
            k: kwargs[k] for k in ('budget', 'max_usd_per_run', 'max_tool_calls', 'request')
            if k in kwargs})
    if status['media'] == 'ready':
        return run_media(run, root=root, live=live, **{
            k: kwargs[k] for k in ('budget', 'max_usd_per_job', 'draft_override')
            if k in kwargs})
    if status['review'] == 'ready' or (
            run['stage'] == 'review' and status['review'] != 'review_required'):
        run['stages']['review'] = {
            'status': 'review_required',
            'completed_at': _utc(),
            'summary': 'Package ready for human review; not publishable',
            'result': review_summary(run),
        }
        run['updated_at'] = _utc()
        _write_run(root, run)
        return run
    raise ValueError('No stage is ready to advance')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='cmd', required=True)

    p_boot = sub.add_parser('bootstrap', help='Show theme, hypotheses, formats, media catalog')
    p_boot.add_argument('--case', default=DEFAULT_CASE)

    p_start = sub.add_parser('start', help='Start a run from the men\'s-health theme case')
    p_start.add_argument('--case', default=DEFAULT_CASE)
    p_start.add_argument('--plan', default=DEFAULT_PLAN)
    p_start.add_argument('--hypothesis', action='append', dest='hypotheses')
    p_start.add_argument('--format', action='append', dest='formats')
    p_start.add_argument('--media', action='append', dest='media')
    p_start.add_argument('--output', default='outputs/pipeline')

    p_adv = sub.add_parser('advance', help='Run the next ready stage (dry-run default)')
    p_adv.add_argument('--run-id', required=True)
    p_adv.add_argument('--output', default='outputs/pipeline')
    p_adv.add_argument('--live', action='store_true')
    p_adv.add_argument('--budget-usd', type=float, default=0)
    p_adv.add_argument('--max-usd-per-search', type=float, default=0)
    p_adv.add_argument('--max-usd-per-run', type=float, default=0)
    p_adv.add_argument('--max-usd-per-job', type=float, default=0)

    p_skip = sub.add_parser('skip', help='Skip research or writing and unlock the next stage')
    p_skip.add_argument('--run-id', required=True)
    p_skip.add_argument('--stage', choices=['research', 'writing'], required=True)
    p_skip.add_argument('--output', default='outputs/pipeline')

    p_show = sub.add_parser('show', help='Show a run')
    p_show.add_argument('--run-id', required=True)
    p_show.add_argument('--output', default='outputs/pipeline')

    p_list = sub.add_parser('list', help='List runs')
    p_list.add_argument('--output', default='outputs/pipeline')

    args = parser.parse_args()
    try:
        if args.cmd == 'bootstrap':
            print(json.dumps(bootstrap(args.case), indent=2))
        elif args.cmd == 'start':
            print(json.dumps(start(
                args.case, args.hypotheses, args.formats, args.media, args.output, args.plan),
                indent=2))
        elif args.cmd == 'advance':
            run = load_run(args.output, args.run_id)
            print(json.dumps(advance(
                run, root=args.output, live=args.live,
                budget=args.budget_usd,
                max_usd_per_search=args.max_usd_per_search,
                max_usd_per_run=args.max_usd_per_run,
                max_usd_per_job=args.max_usd_per_job), indent=2))
        elif args.cmd == 'skip':
            run = load_run(args.output, args.run_id)
            print(json.dumps(skip_stage(run, args.stage, args.output), indent=2))
        elif args.cmd == 'show':
            print(json.dumps(load_run(args.output, args.run_id), indent=2))
        elif args.cmd == 'list':
            print(json.dumps(list_runs(args.output), indent=2))
    except (ValueError, OSError, RuntimeError, KeyError, TypeError, FileNotFoundError) as exc:
        parser.exit(1, f'Pipeline blocked: {exc}\n')


if __name__ == '__main__':
    main()
