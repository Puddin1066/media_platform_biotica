"""One-command private assembly from an approved episode input directory.

Expected files: storyboard.json, footage-plan.json, plate.mp4 and audio/<beat>.
Optional plate-options.json sets {"start_seconds": 0, "loop": false}.
Plan media sources must be relative to the input directory. The files stay
outside git; the command creates a Remotion package, not a publish approval.
"""
import argparse
import json
import subprocess
from pathlib import Path

from remotion_handoff import package
from speech_timing import BEATS, assemble


def prepare(input_dir, remotion_dir):
    base = Path(input_dir).resolve(strict=True)
    board = json.loads((base / 'storyboard.json').read_text())
    plan = json.loads((base / 'footage-plan.json').read_text())
    if board.get('script_sha256') != plan.get('script_sha256'):
        raise ValueError('Storyboard and selected footage must pin the same script')
    for shot in plan['shots']:
        source = Path(shot['media_source'])
        if source.is_absolute():
            raise ValueError('Production bundle media paths must be relative')
        resolved = (base / source).resolve(strict=True)
        if not resolved.is_relative_to(base) or not resolved.is_file():
            raise ValueError('Media source must stay inside the private input directory')
        shot['media_source'] = str(resolved)
    audio = {}
    for beat in BEATS:
        matches = [base / 'audio' / (beat + ext) for ext in ('.wav', '.mp3', '.m4a')]
        audio[beat] = next((p for p in matches if p.is_file()), None)
        if audio[beat] is None or not audio[beat].resolve().is_relative_to(base):
            raise ValueError('Missing or external audio for ' + beat)
    plate = (base / 'plate.mp4').resolve(strict=True)
    if not plate.is_relative_to(base):
        raise ValueError('Plate must stay inside the private input directory')
    outputs = base / 'generated'
    options_file = base / 'plate-options.json'
    options = json.loads(options_file.read_text()) if options_file.exists() else {}
    if set(options) - {'start_seconds', 'loop'} or \
            type(options.get('loop', False)) is not bool:
        raise ValueError('Invalid plate options')
    graphics_file = base / 'graphics.json'
    if graphics_file.exists():
        graphics = json.loads(graphics_file.read_text(encoding='utf-8'))
        headline = graphics.get('headline')
        if set(graphics) != {'headline'} or not isinstance(headline, str) or \
                not 1 <= len(headline.strip()) <= 55:
            raise ValueError('Graphics headline must be 1–55 characters')
        plan['headline'] = headline.strip()
    timing = assemble(board, audio, outputs / 'narration.wav', outputs / 'timing.json')
    manifest = package(plan, plate, remotion_dir, outputs / 'narration.wav',
                       plate_start=options.get('start_seconds', 0),
                       loop_plate=options.get('loop', False), timing=timing)
    return manifest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input-dir', required=True)
    p.add_argument('--remotion-dir', default='remotion')
    p.add_argument('--render', action='store_true', help='Run npm Remotion render after packaging')
    args = p.parse_args()
    manifest = prepare(args.input_dir, args.remotion_dir)
    if args.render:
        subprocess.run(['npm', 'run', 'render'], cwd=args.remotion_dir, check=True)
    print(manifest)


if __name__ == '__main__':
    main()
