"""Production gates and provider handoff use fictional scripts and fake clients."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import remotion_handoff
import runway_media
import speech_timing
import production_job


def board():
    return {'status': 'awaiting_footage', 'script_sha256': 'fictional-hash',
            'cues': [{'cue_id': beat, 'spoken_text': 'Fictional test words only.',
                      'claim_ids': ['fictional']} for beat in speech_timing.BEATS]}


class ProductionTests(unittest.TestCase):
    def test_measured_audio_gates_runtime_and_preserves_beat_order(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            files = {b: root / (b + '.wav') for b in speech_timing.BEATS}
            for path in files.values():
                path.touch()
            with patch.object(speech_timing, 'duration', return_value=5), \
                    patch.object(speech_timing, 'run_ffmpeg') as ffmpeg:
                timing = speech_timing.assemble(board(), files, root / 'voice.wav', root / 'timing.json')
            self.assertEqual([s['start_frame'] for s in timing['segments']],
                             [0, 150, 300, 450, 600])
            self.assertEqual(timing['segments'][-1]['end_frame'], 750)
            self.assertEqual(ffmpeg.call_count, 1)
            with patch.object(speech_timing, 'duration', return_value=7):
                with self.assertRaisesRegex(ValueError, 'exceeds 30 seconds'):
                    speech_timing.assemble(board(), files, root / 'voice.wav', root / 'timing.json')

    def test_footage_follows_spoken_beats_and_caption_shape(self):
        timing = {'status': 'timed_review_required', 'fps': 30, 'duration_frames': 900,
                  'script_sha256': 'fictional-hash',
                  'segments': [{'cue_id': beat, 'start_frame': i * 150,
                                'end_frame': (i + 1) * 150,
                                'text': 'These are five fictional test words.',
                                'claim_ids': ['fictional']}
                               for i, beat in enumerate(speech_timing.BEATS)]}
        plan = {'script_sha256': 'fictional-hash', 'shots': [
            {'cue_id': beat} for beat in (*speech_timing.BEATS, 'next_test')]}
        layout = remotion_handoff.timed_layout(plan, timing)
        # The final beat spans 600–900, so each of its two shots gets 150 frames.
        self.assertEqual(layout[-2:], [(600, 150), (750, 150)])
        captions = remotion_handoff.captions_from_timing(timing)
        self.assertEqual(captions[0]['confidence'], None)
        self.assertEqual([c['text'] for c in captions[:2]],
                         ['These are five', 'fictional test words.'])
        self.assertEqual(captions[-1]['endMs'], 25000)
        timing['script_sha256'] = 'stale'
        with self.assertRaisesRegex(ValueError, 'match'):
            remotion_handoff.timed_layout(plan, timing)

    def test_runway_submits_once_and_collects_known_task(self):
        with tempfile.TemporaryDirectory() as root:
            fake = Mock()
            fake.text_to_speech.create.return_value = SimpleNamespace(id='task-fixture')
            result = runway_media.submit_tts(board(), 'opening', 'Vincent', root,
                                             client=fake, live=True)
            self.assertEqual(result['state'], 'submitted')
            with self.assertRaises(FileExistsError):
                runway_media.submit_tts(board(), 'opening', 'Vincent', root,
                                        client=fake, live=True)
            self.assertEqual(fake.text_to_speech.create.call_count, 1)
            fake.tasks.retrieve.return_value = SimpleNamespace(
                status='SUCCEEDED', output=['https://example.test/fixture.mp3'])
            output = Path(root) / 'opening.mp3'
            with patch.object(runway_media, 'download_output', side_effect=lambda u, p:
                              Path(p).write_bytes(b'fictional audio')):
                collected = runway_media.collect(result['record'], output, client=fake)
            self.assertEqual(collected['state'], 'collected')
            with self.assertRaisesRegex(ValueError, 'cannot be collected twice'):
                runway_media.collect(result['record'], output, client=fake)

    def test_avatar_and_act_two_are_separate_optional_runway_jobs(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            audio, plate, performance = (root / 'voice.wav', root / 'plate.mp4',
                                         root / 'performance.mp4')
            for file in (audio, plate, performance):
                file.write_bytes(b'fictional media')
            fake = Mock()
            fake.uploads.create_ephemeral.return_value = SimpleNamespace(uri='runway://fixture')
            fake.avatar_videos.create.return_value = SimpleNamespace(id='avatar-fixture')
            fake.character_performance.create.return_value = SimpleNamespace(id='act-two-fixture')
            with patch.object(runway_media, 'duration', return_value=10):
                avatar = runway_media.submit_avatar('my-approved-avatar', audio, root,
                                                    client=fake, live=True)
                act = runway_media.submit_act_two(plate, performance, root,
                                                  client=fake, live=True)
            self.assertEqual(avatar['task_id'], 'avatar-fixture')
            self.assertEqual(act['task_id'], 'act-two-fixture')
            self.assertEqual(fake.character_performance.create.call_args.kwargs['model'], 'act_two')

    def test_private_job_rejects_media_outside_input_directory(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / 'input'
            base.mkdir()
            (base / 'storyboard.json').write_text(json.dumps(board()))
            (base / 'footage-plan.json').write_text(json.dumps({
                'script_sha256': 'fictional-hash',
                'shots': [{'media_source': '../external.mp4'}]}))
            (Path(root) / 'external.mp4').touch()
            with self.assertRaisesRegex(ValueError, 'inside'):
                production_job.prepare(base, Path(root) / 'remotion')


if __name__ == '__main__':
    unittest.main()
