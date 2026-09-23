"""Generate an unmistakably fictional episode for GitHub Actions integration QC.

No API calls, medical claims, downloaded creator media or paid credentials.
The tone and test pattern exercise the real packager and Remotion composition.
"""
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from pipeline import discover_for_script, plan_from_script
import pipeline
from production_job import prepare
from speech_timing import BEATS


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)


def main():
    root = Path('outputs/offline-fixture')
    root.mkdir(parents=True, exist_ok=True)
    plate, clip, visual = root / 'plate.mp4', root / 'clip.mp4', root / 'visual.mp4'
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=540x960:rate=30', '-t', '10',
           '-pix_fmt', 'yuv420p', str(plate))
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-t', '5',
           '-pix_fmt', 'yuv420p', str(clip))
    ffmpeg('-f', 'lavfi', '-i', 'smptebars=size=640x360:rate=30', '-t', '5',
           '-pix_fmt', 'yuv420p', str(visual))
    board = {'status': 'awaiting_footage', 'script_sha256': 'fictional-fixture',
             'reviewer': 'Synthetic fixture',
             'topic': 'fictional visual test',
             'cues': [{'cue_id': beat, 'spoken_text': 'This is a fictional pipeline test.',
                       'claim_ids': ['fictional-fixture'], 'search_query': beat}
                      for beat in BEATS]}
    (root / 'audio').mkdir(exist_ok=True)
    for index, beat in enumerate(BEATS):
        path = root / 'audio' / (beat + '.wav')
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=%s:sample_rate=48000' % (300 + 80 * index),
               '-t', '5', str(path))
    # Lead bundles model collected assets. Search is replaced with empty results:
    # this offline fixture never contacts Commons, YouTube, Instagram or Runway.
    leads = [{'cue_id': beat, 'candidates': [
        {'id': 'fixture:' + beat, 'provider': 'fixture', 'rights_status': 'review_required'}]}
             for beat in BEATS]
    leads.append({'cue_id': BEATS[-1], 'candidates': [
        {'id': 'runway:synthetic', 'provider': 'runway', 'visual_type': 'illustration',
         'rights_status': 'review_required'}]})
    with patch.object(pipeline, 'discover', return_value={'candidates': []}):
        catalog = discover_for_script(board, instagram_catalogs=leads)
    approvals = [{'candidate_id': 'fixture:' + beat, 'cue_id': beat,
                  'rights_status': 'approved', 'license_basis': 'Synthetic test pattern',
                  'credit': 'Synthetic fixture', 'media_source': 'clip.mp4',
                  'start_seconds': 0} for beat in BEATS]
    approvals.append({'candidate_id': 'runway:synthetic', 'cue_id': BEATS[-1],
                      'rights_status': 'approved', 'license_basis': 'Synthetic test pattern',
                      'credit': 'Synthetic illustration', 'media_source': 'visual.mp4',
                      'start_seconds': 0, 'visual_type': 'illustration'})
    plan = plan_from_script(board, catalog, approvals, media_root=root)
    assert plan['shots'][-1]['visual_type'] == 'illustration'
    assert all(not Path(shot['media_source']).is_absolute() for shot in plan['shots'])
    (root / 'storyboard.json').write_text(json.dumps(board))
    (root / 'footage-plan.json').write_text(json.dumps(plan))
    (root / 'plate-options.json').write_text(json.dumps({'loop': True}))
    (root / 'graphics.json').write_text(json.dumps({'headline': 'SYNTHETIC EPISODE TEST'}))
    manifest_path = prepare(root, 'remotion')
    manifest = json.loads(manifest_path.read_text())
    assert manifest['shots'][-1]['visual_type'] == 'illustration'
    assert len(manifest['shots']) == 6
    manifest['fixture'] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(manifest_path)


if __name__ == '__main__':
    main()
