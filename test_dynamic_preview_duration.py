import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import remotion_handoff
import speech_timing


class DynamicPreviewDurationTests(unittest.TestCase):
    def _board(self, dynamic=True):
        board = {
            'status': 'awaiting_footage',
            'script_sha256': 'dynamic-preview-test',
            'cues': [
                {'cue_id': beat, 'spoken_text': beat, 'claim_ids': []}
                for beat in speech_timing.BEATS
            ],
        }
        if dynamic:
            board['review_status'] = 'unreviewed_web_preview'
        return board

    def test_unreviewed_preview_can_exceed_thirty_seconds(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {}
            for beat in speech_timing.BEATS:
                path = root / f'{beat}.mp3'
                path.write_bytes(b'x')
                files[beat] = path
            timing_path = root / 'timing.json'
            with patch.object(speech_timing, 'duration', return_value=8.0), \
                    patch.object(speech_timing, 'run_ffmpeg') as ffmpeg:
                timing = speech_timing.assemble(
                    self._board(dynamic=True), files, root / 'voice.wav', timing_path)
            self.assertEqual(timing['duration_frames'], 1200)
            self.assertEqual(timing['format_mode'], 'dynamic_preview')
            self.assertEqual(timing['segments'][-1]['end_frame'], 1200)
            self.assertIn('atrim=duration=40.000000', ffmpeg.call_args.args[0])
            self.assertEqual(json.loads(timing_path.read_text())['duration_frames'], 1200)

            plan = {
                'script_sha256': 'dynamic-preview-test',
                'shots': [
                    {'cue_id': 'opening'},
                    {'cue_id': 'explanations'},
                    {'cue_id': 'evidence'},
                    {'cue_id': 'limits'},
                    {'cue_id': 'next_test'},
                    {'cue_id': 'next_test'},
                ],
            }
            layout = remotion_handoff.timed_layout(plan, timing)
            self.assertEqual(layout[-2:], [(960, 120), (1080, 120)])

    def test_non_preview_format_retains_thirty_second_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            files = {}
            for beat in speech_timing.BEATS:
                path = root / f'{beat}.mp3'
                path.write_bytes(b'x')
                files[beat] = path
            with patch.object(speech_timing, 'duration', return_value=8.0):
                with self.assertRaisesRegex(ValueError, 'exceeds 30 seconds'):
                    speech_timing.assemble(
                        self._board(dynamic=False), files,
                        root / 'voice.wav', root / 'timing.json')


if __name__ == '__main__':
    unittest.main()
