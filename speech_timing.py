"""Turn five independently recorded speech beats into one timed narration track.

Beat boundaries come from measured audio lengths, not guessed word counts. The
output JSON is bound to the reviewed storyboard and drives captions and inset
changes in Remotion. This module does not synthesize speech or publish media.
"""
import argparse
import json
import math
from pathlib import Path

from footage import run_ffmpeg
from remotion_handoff import duration

BEATS = ('opening', 'explanations', 'evidence', 'limits', 'next_test')
FPS = 30
FRAMES = 900


def assemble(board, files, output_audio, output_timing):
    if board.get('status') != 'awaiting_footage' or \
            tuple(c.get('cue_id') for c in board.get('cues', [])) != BEATS:
        raise ValueError('Reviewed five-beat storyboard required')
    if set(files) != set(BEATS):
        raise ValueError('Supply a recorded audio file for every beat')
    paths = [Path(files[beat]) for beat in BEATS]
    if any(not path.is_file() for path in paths):
        raise ValueError('A beat audio file is missing')
    lengths = [duration(path) for path in paths]
    if any(not math.isfinite(t) or t <= 0 for t in lengths):
        raise ValueError('Invalid audio duration')
    # Round cumulative boundaries so every beat begins on a video frame.
    ends = [round(sum(lengths[:i + 1]) * FPS) for i in range(len(lengths))]
    if ends[-1] > FRAMES or any(b <= a for a, b in zip([0] + ends[:-1], ends)):
        raise ValueError('Speech exceeds 30 seconds or a beat is too short for one frame')
    segments = [{'cue_id': beat, 'start_frame': start, 'end_frame': end,
                 'text': cue['spoken_text'], 'claim_ids': cue['claim_ids']}
                for beat, cue, start, end in zip(BEATS, board['cues'], [0] + ends[:-1], ends)]
    output_audio, output_timing = Path(output_audio), Path(output_timing)
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    output_timing.parent.mkdir(parents=True, exist_ok=True)
    # Convert to PCM, concatenate in reviewed order, and pad the episode tail.
    chain = ''.join('[%d:a]' % i for i in range(5)) + \
            'concat=n=5:v=0:a=1,aresample=48000,apad,atrim=duration=30[out]'
    run_ffmpeg([arg for path in paths for arg in ('-i', str(path))] +
               ['-filter_complex', chain, '-map', '[out]', '-c:a', 'pcm_s16le',
                str(output_audio)])
    timing = {'schema_version': 1, 'fps': FPS, 'duration_frames': FRAMES,
              'script_sha256': board['script_sha256'], 'segments': segments,
              'audio_seconds': sum(lengths), 'status': 'timed_review_required'}
    output_timing.write_text(json.dumps(timing, indent=2) + '\n', encoding='utf-8')
    return timing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--storyboard', required=True)
    for beat in BEATS:
        parser.add_argument('--' + beat.replace('_', '-'), required=True)
    parser.add_argument('--output-audio', required=True)
    parser.add_argument('--output-timing', required=True)
    args = parser.parse_args()
    files = {beat: getattr(args, beat) for beat in BEATS}
    assemble(json.loads(Path(args.storyboard).read_text()), files,
             args.output_audio, args.output_timing)
    print(args.output_timing)


if __name__ == '__main__':
    main()
