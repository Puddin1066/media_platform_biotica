"""Generate an unmistakably fictional episode for GitHub Actions integration QC.

No API calls, medical claims, downloaded creator media or paid credentials.
The tone and test pattern exercise the real packager and Remotion composition.
"""
import json
import subprocess
from pathlib import Path

from production_job import prepare
from speech_timing import BEATS


def ffmpeg(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)


def main():
    root = Path('outputs/offline-fixture')
    root.mkdir(parents=True, exist_ok=True)
    plate, clip = root / 'plate.mp4', root / 'clip.mp4'
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=540x960:rate=30', '-t', '10',
           '-pix_fmt', 'yuv420p', str(plate))
    ffmpeg('-f', 'lavfi', '-i', 'testsrc2=size=640x360:rate=30', '-t', '5',
           '-pix_fmt', 'yuv420p', str(clip))
    board = {'status': 'awaiting_footage', 'script_sha256': 'fictional-fixture',
             'cues': [{'cue_id': beat, 'spoken_text': 'This is a fictional pipeline test.',
                       'claim_ids': ['fictional-fixture']} for beat in BEATS]}
    (root / 'audio').mkdir(exist_ok=True)
    for index, beat in enumerate(BEATS):
        path = root / 'audio' / (beat + '.wav')
        ffmpeg('-f', 'lavfi', '-i', 'sine=frequency=%s:sample_rate=48000' % (300 + 80 * index),
               '-t', '5', str(path))
    plan = {'status': 'renderable_not_publish_approved', 'target_seconds': 30,
            'script_sha256': board['script_sha256'],
            'shots': [{'destination_seconds': i * 5, 'duration_seconds': 5,
                       'start_seconds': 0, 'media_source': 'clip.mp4',
                       'license_basis': 'Generated test pattern', 'credit': 'Synthetic fixture',
                       'cue_id': beat, 'claim_ids': ['fictional-fixture']}
                      for i, beat in enumerate((*BEATS, BEATS[-1]))]}
    (root / 'storyboard.json').write_text(json.dumps(board))
    (root / 'footage-plan.json').write_text(json.dumps(plan))
    (root / 'plate-options.json').write_text(json.dumps({'loop': True}))
    (root / 'graphics.json').write_text(json.dumps({'headline': 'SYNTHETIC EPISODE TEST'}))
    manifest_path = prepare(root, 'remotion')
    manifest = json.loads(manifest_path.read_text())
    manifest['fixture'] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(manifest_path)


if __name__ == '__main__':
    main()
