"""Package independently produced assets for the Remotion Reel composition."""
import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path

from footage import run_ffmpeg, safe_media_source
from studio import digest


def duration(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                             'format=duration', '-of', 'default=nokey=1:noprint_wrappers=1',
                             str(path)], check=True, capture_output=True, text=True, timeout=30)
    return float(result.stdout.strip())


def timed_layout(plan, timing):
    """Place every selected shot inside its reviewed spoken beat."""
    if timing.get('status') != 'timed_review_required' or \
            timing.get('script_sha256') != plan.get('script_sha256') or \
            timing.get('duration_frames') != 900 or timing.get('fps') != 30:
        raise ValueError('Speech timing must match the approved script and 30-second format')
    segments = timing.get('segments', [])
    names = ('opening', 'explanations', 'evidence', 'limits', 'next_test')
    if [s.get('cue_id') for s in segments] != list(names):
        raise ValueError('Speech timing needs the five ordered beats')
    previous = 0
    for segment in segments:
        if segment.get('start_frame') != previous or \
                type(segment.get('end_frame')) is not int or \
                not previous < segment['end_frame'] <= 900 or \
                not isinstance(segment.get('text'), str) or not segment['text'].strip():
            raise ValueError('Speech beats must have contiguous valid frame boundaries')
        previous = segment['end_frame']
    slots = {}
    for index, shot in enumerate(plan['shots']):
        if shot.get('cue_id') not in names:
            raise ValueError('Every shot needs a reviewed spoken cue')
        slots.setdefault(shot['cue_id'], []).append(index)
    if set(slots) != set(names):
        raise ValueError('Every spoken beat needs a shot')
    layout = [None] * len(plan['shots'])
    for index, segment in enumerate(segments):
        start = segment['start_frame']
        end = segments[index + 1]['start_frame'] if index < 4 else 900
        selected = slots[segment['cue_id']]
        boundaries = [start + round((end - start) * i / len(selected))
                      for i in range(len(selected) + 1)]
        for shot_index, first, last in zip(selected, boundaries, boundaries[1:]):
            if last <= first:
                raise ValueError('Beat is too short for its selected shots')
            layout[shot_index] = (first, last - first)
    return layout


def captions_from_timing(timing):
    """Readable phrase captions with estimated within-beat timing for review."""
    captions = []
    for segment in timing['segments']:
        words = segment['text'].split()
        phrases = [' '.join(words[i:i + 5]) for i in range(0, len(words), 5)]
        start, end = segment['start_frame'], segment['end_frame']
        for i, phrase in enumerate(phrases):
            first = start + round((end - start) * i / len(phrases))
            last = start + round((end - start) * (i + 1) / len(phrases))
            if last <= first:
                raise ValueError('Caption phrases exceed the available speech frames')
            captions.append({'text': phrase, 'startMs': round(first * 1000 / 30),
                             'endMs': round(last * 1000 / 30),
                             'timestampMs': None, 'confidence': None})
    return captions


def package(plan, plate, output_dir, voice=None, plate_start=0, loop_plate=False,
            timing=None):
    """Trim reviewed sources as separate silent pieces; Remotion does final assembly."""
    if plan.get('status') != 'renderable_not_publish_approved' or \
            plan.get('target_seconds') != 30 or len(plan.get('shots', [])) != 6:
        raise ValueError('Expected reviewed 30-second, six-shot footage plan')
    plate = Path(safe_media_source(plate))
    if not plate.is_file() or not math.isfinite(plate_start) or plate_start < 0:
        raise ValueError('A local plate and nonnegative start time are required')
    plate_duration = duration(plate)
    if plate_start >= plate_duration or (not loop_plate and plate_start + 30 > plate_duration):
        raise ValueError('Plate is too short; select an earlier start or explicitly loop it')
    if voice:
        voice = Path(voice)
        if not voice.is_file() or duration(voice) < 30:
            raise ValueError('Voice track must be a local file at least 30 seconds long')
        if voice.suffix.lower() not in {'.wav', '.mp3', '.m4a'}:
            raise ValueError('Voice track must be WAV, MP3 or M4A')
    if timing is not None and voice is None:
        raise ValueError('Timed captions require a separate narration track')
    layout = timed_layout(plan, timing) if timing is not None else [(i * 150, 150)
                                                                    for i in range(6)]
    output_dir = Path(output_dir)
    assets = output_dir / 'public' / 'assets'
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(plate, assets / 'plate.mp4')
    if voice:
        shutil.copyfile(voice, assets / ('voice' + voice.suffix.lower()))
    shots = []
    for index, shot in enumerate(plan['shots']):
        if shot.get('destination_seconds') != index * 5 or \
                shot.get('duration_seconds') != 5 or not shot.get('license_basis') or \
                not shot.get('credit'):
            raise ValueError('Shots must be reviewed five-second intervals in timeline order')
        source = safe_media_source(shot['media_source'])
        filename = 'shot%02d.mp4' % index
        run_ffmpeg(['-ss', str(shot['start_seconds']), '-i', source, '-t', '5', '-an',
                    '-vf', 'scale=640:360:force_original_aspect_ratio=decrease,'
                           'pad=640:360:(ow-iw)/2:(oh-ih)/2',
                    '-r', '30', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                    str(assets / filename)])
        if duration(assets / filename) < 4.9:
            raise ValueError('Selected footage interval is shorter than five seconds')
        shots.append({'src': 'assets/' + filename, 'from': layout[index][0],
                      'duration': layout[index][1], 'credit': shot['credit'],
                      'playback_rate': shot.get('playback_rate', 1),
                      'cue_id': shot.get('cue_id'), 'claim_ids': shot.get('claim_ids', [])})
    manifest = {'schema_version': 1, 'fps': 30, 'width': 1080, 'height': 1920,
                'duration_frames': 900, 'plate': 'assets/plate.mp4',
                'plate_start_frames': round(plate_start * 30), 'loop_plate': loop_plate,
                'voice': 'assets/voice' + voice.suffix.lower() if voice else None,
                'shots': shots,
                'captions': captions_from_timing(timing) if timing else [],
                'caption_timing': 'estimated_within_measured_beats' if timing else 'none',
                'script_sha256': plan.get('script_sha256'),
                'footage_plan_sha256': digest(plan), 'status': 'preview_only'}
    target = output_dir / 'public' / 'episode.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--plate', required=True)
    parser.add_argument('--voice', help='Optional 30-second narration; mutes plate audio')
    parser.add_argument('--timing', help='Speech timing JSON from speech_timing.py')
    parser.add_argument('--plate-start', type=float, default=0)
    parser.add_argument('--loop-plate', action='store_true')
    parser.add_argument('--output-dir', default='remotion')
    args = parser.parse_args()
    print(package(json.loads(Path(args.plan).read_text()), args.plate,
                  args.output_dir, args.voice, args.plate_start, args.loop_plate,
                  json.loads(Path(args.timing).read_text()) if args.timing else None))


if __name__ == '__main__':
    main()
