"""Regression checks for the paid integration, using fake transport and real journals."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import runway_host as host
import runway_operation as operations
import studio_media


class MissingObject(Exception):
    response = {'Error': {'Code': 'NoSuchKey'}}


class HostIntegrationTests(unittest.TestCase):
    def storage(self):
        objects = {}
        def persist(path, key):
            objects[key] = Path(path).read_bytes()
            return {'key': key, 'url': 'https://media.test/' + key,
                    'sha256': host.runway_media.digest_file(path)}
        def fetch(key, target):
            if key not in objects:
                raise MissingObject()
            target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(objects[key])
            return {'key': key, 'sha256': host.runway_media.digest_file(target)}
        return objects, persist, fetch

    def test_cold_runner_resumes_known_task_without_new_submission(self):
        objects, persist, fetch = self.storage()
        real_execute = operations.execute
        calls = []
        def call(method, path, body=None, query=None):
            calls.append((method, path))
            if path == '/v1/organization': return {'creditBalance': 1000}
            if method == 'POST': return {'id': 'task'}
            return {'status': 'SUCCEEDED', 'output': ['https://media.test/out.mp4']}
        def archive(response, identifier, work):
            work.mkdir(parents=True, exist_ok=True)
            output = work / 'out.mp4'; output.write_bytes(b'generated output fixture')
            return [persist(output, 'generated/' + identifier)]
        def execute(request, **kwargs):
            return real_execute(request, call=call, archive=archive, **kwargs)
        body = {'model': 'aleph2', 'videoUri': 'https://media.test/source.mp4', 'promptText': 'lab'}
        with tempfile.TemporaryDirectory() as directory, patch.object(host.media_store, 'persist', side_effect=persist), patch.object(host.media_store, 'fetch', side_effect=fetch), patch.object(operations, 'execute', side_effect=execute):
            root = Path(directory)
            _, first = host.operation('post_video_to_video', body, 112, root/'first', root/'work-first')
            self.assertEqual(sum(method == 'POST' for method, _ in calls), 1)
            calls.clear()
            _, second = host.operation('post_video_to_video', body, 112, root/'second', root/'work-second')
            self.assertEqual(first, second)
            self.assertEqual(calls, [])
            self.assertTrue(any(key.endswith('/result.json') for key in objects))

    def test_ambiguous_submission_remains_reserved_on_cold_runner(self):
        _, persist, fetch = self.storage()
        real_execute = operations.execute
        calls = []
        def call(method, path, body=None, query=None):
            if method == 'GET': return {'creditBalance': 1000}
            calls.append(path)
            raise TimeoutError('No submission response')
        def execute(request, **kwargs):
            return real_execute(request, call=call, **kwargs)
        body = {'model': 'aleph2', 'videoUri': 'https://media.test/source.mp4'}
        with tempfile.TemporaryDirectory() as directory, patch.object(host.media_store, 'persist', side_effect=persist), patch.object(host.media_store, 'fetch', side_effect=fetch), patch.object(operations, 'execute', side_effect=execute):
            root = Path(directory)
            with self.assertRaises(TimeoutError): host.operation('post_video_to_video', body, 112, root/'first', root/'work')
            with self.assertRaisesRegex(ValueError, 'reserved_unknown'): host.operation('post_video_to_video', body, 112, root/'second', root/'work')
            self.assertEqual(len(calls), 1)

    @unittest.skipUnless(shutil.which('ffmpeg'), 'FFmpeg required')
    def test_prepared_input_is_restored_without_reencoding_on_another_runner(self):
        _, persist, fetch = self.storage()
        with tempfile.TemporaryDirectory() as directory, patch.object(host.media_store, 'persist', side_effect=persist), patch.object(host.media_store, 'fetch', side_effect=fetch):
            root = Path(directory); source = root/'source.mp4'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=s=256x256:r=24:d=4', '-c:v', 'libx264', str(source)], check=True)
            _, original = host.prepared_video(source, 4, 0, root/'first')
            original_run = subprocess.run
            def probe_only(command, **kwargs):
                if command[0] == 'ffmpeg': raise AssertionError('Must restore original bytes')
                return original_run(command, **kwargs)
            with patch.object(host.subprocess, 'run', side_effect=probe_only):
                _, reused = host.prepared_video(source, 4, 0, root/'second')
            self.assertEqual(original['sha256'], reused['sha256'])
            self.assertEqual(original['url'], reused['url'])

    def test_storage_permission_errors_never_trigger_generation(self):
        with patch.object(host.media_store, 'fetch', side_effect=PermissionError('R2 denied')):
            with self.assertRaises(PermissionError): host.restore('key', 'file')

    def test_rich_overlay_can_partition_a_sentence_without_overlap(self):
        script = {'script': [{'sentence_id': 's01', 'text': 'A long spoken finding.'}]}
        shots = [{'shot_id': 'setup', 'sentence_ids': ['s01'], 'start_fraction': 0, 'end_fraction': .5},
                 {'shot_id': 'payoff', 'sentence_ids': ['s01'], 'start_fraction': .5, 'end_fraction': 1}]
        self.assertEqual(len(studio_media.compile_shots(script, {'shots': shots})), 2)
        shots[1]['start_fraction'] = .4
        with self.assertRaisesRegex(ValueError, 'overlap'): studio_media.compile_shots(script, {'shots': shots})
        shots[1]['start_fraction'] = .6
        with self.assertRaisesRegex(ValueError, 'gaps'): studio_media.compile_shots(script, {'shots': shots})

    def test_images_use_spoken_context_and_survive_a_replacement_runner(self):
        _, persist, fetch = self.storage()
        script = {"title": "Finding", "script": [{"sentence_id": "s01", "text": "The science is easier than this cardio."}]}
        plan = {"shots": [{"shot_id": "joke", "sentence_ids": ["s01"], "type": "joke_visual", "intent": "A treadmill running away from its owner", "humor_device": "self-deprecation"}]}
        with tempfile.TemporaryDirectory() as directory, patch.object(host.media_store, 'persist', side_effect=persist), patch.object(host.media_store, 'fetch', side_effect=fetch), patch.object(studio_media.openai_stills, 'generate_still_bytes', return_value=b'image fixture') as generate:
            for runner in ('first', 'second'):
                root = Path(directory) / runner
                artifacts, _ = studio_media.paths(root, 'episode')
                studio_media.write(artifacts/'canonical_script.json', script)
                studio_media.write(artifacts/'visual_plan.json', plan)
                studio_media.run_assets(root, 'episode', {}, '')
            self.assertEqual(generate.call_count, 1)
            self.assertIn(script['script'][0]['text'], generate.call_args.args[0])
            self.assertIn('self-deprecation', generate.call_args.args[0])

    def test_short_driver_windows_keep_measured_words_and_minimum_duration(self):
        timing = {'duration_ms': 10000, 'captions': [{'startMs': x} for x in range(0, 10000, 500)]}
        segments = studio_media.qualified_host_segments(timing)
        self.assertEqual(segments[0][0], 0)
        self.assertEqual(segments[-1][1], 10000)
        self.assertTrue(all(3000 <= end-start <= 4000 for start, end in segments))
        self.assertEqual([end for _, end in segments[:-1]], [start for start, _ in segments[1:]])

if __name__ == '__main__': unittest.main()
