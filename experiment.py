"""Compare Instagram Reel variants at the same post-publication age.

This is a descriptive test of Biotica creative, not evidence that a source
creator's popular video segment will retain Biotica's audience. Do not infer
causation from two organic posts with different delivery or audiences.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path


def metric_value(snapshot, name):
    for row in snapshot['metrics']:
        if row.get('name') != name:
            continue
        if 'total_value' in row:
            value = row['total_value']
            return value.get('value') if isinstance(value, dict) else value
        if row.get('values'):
            return row['values'][-1].get('value')
    return None


def compare(variants, target_hours=48, tolerance_hours=6, min_views=100):
    """Require comparable capture ages and return only measured available data."""
    if len(variants) < 2:
        raise ValueError('At least two variants required')
    rows = []
    for item in variants:
        post_time = datetime.fromisoformat(item['published_at'].replace('Z', '+00:00'))
        snapshot = item['snapshot']
        read_time = datetime.fromisoformat(snapshot['retrieved_at'].replace('Z', '+00:00'))
        age = (read_time - post_time).total_seconds() / 3600
        if abs(age - target_hours) > tolerance_hours:
            raise ValueError('Snapshot ages do not match the comparison window')
        views = metric_value(snapshot, 'views')
        if not isinstance(views, (int, float)) or views < min_views:
            raise ValueError('Insufficient measured views for a comparison')
        shares, saves = metric_value(snapshot, 'shares'), metric_value(snapshot, 'saved')
        rows.append({'variant': item['variant'], 'media_id': snapshot['media_id'],
                     'age_hours': round(age, 1), 'views': views,
                     'shares_per_1000_views': round(shares * 1000 / views, 2)
                     if isinstance(shares, (int, float)) else None,
                     'saves_per_1000_views': round(saves * 1000 / views, 2)
                     if isinstance(saves, (int, float)) else None,
                     'avg_watch_time': metric_value(snapshot, 'ig_reels_avg_watch_time')})
    return {'status': 'descriptive_comparison', 'target_age_hours': target_hours,
            'variants': rows, 'caveat': 'Organic variants are not randomized; account for '
            'audience, distribution, topic, hook and timing before attributing a difference.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--experiment', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    manifest = json.loads(Path(args.experiment).read_text())
    variants = [{**row, 'snapshot': json.loads(Path(row['snapshot_path']).read_text())}
                for row in manifest['variants']]
    result = compare(variants, manifest.get('target_hours', 48))
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(path)


if __name__ == '__main__':
    main()
