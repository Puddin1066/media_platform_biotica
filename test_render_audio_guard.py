import unittest
from unittest import mock

import render_audio_guard


class RenderAudioGuardTests(unittest.TestCase):
    def test_volume_stats_parses_ffmpeg_output(self):
        stderr = """
        [Parsed_volumedetect_0] mean_volume: -24.4 dB
        [Parsed_volumedetect_0] max_volume: -7.2 dB
        """
        completed = mock.Mock(returncode=0, stdout="", stderr=stderr)
        with mock.patch("render_audio_guard.subprocess.run", return_value=completed):
            mean_db, max_db = render_audio_guard.volume_stats(mock.Mock())
        self.assertEqual(mean_db, -24.4)
        self.assertEqual(max_db, -7.2)

    def test_volume_stats_rejects_silence(self):
        stderr = """
        [Parsed_volumedetect_0] mean_volume: -inf dB
        [Parsed_volumedetect_0] max_volume: -inf dB
        """
        completed = mock.Mock(returncode=0, stdout="", stderr=stderr)
        with mock.patch("render_audio_guard.subprocess.run", return_value=completed):
            mean_db, max_db = render_audio_guard.volume_stats(mock.Mock())
        self.assertEqual(mean_db, float("-inf"))
        self.assertEqual(max_db, float("-inf"))

    def test_validate_requires_single_aac_48k_stereo_stream(self):
        info = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
            "format": {"duration": "49.5"},
        }
        with mock.patch("render_audio_guard.probe", return_value=info), \
             mock.patch("render_audio_guard.volume_stats", return_value=(-20.0, -3.0)), \
             mock.patch("render_audio_guard.duration_seconds", side_effect=[49.5, 49.4]):
            stats = render_audio_guard.validate(mock.Mock(), mock.Mock())
        self.assertEqual(stats["status"], "audible_master_narration_confirmed")
        self.assertEqual(stats["sample_rate"], 48000)

    def test_validate_rejects_inaudible_render(self):
        info = {
            "streams": [
                {"codec_type": "video", "codec_name": "h264"},
                {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
            ],
            "format": {"duration": "49.5"},
        }
        with mock.patch("render_audio_guard.probe", return_value=info), \
             mock.patch("render_audio_guard.volume_stats", return_value=(-60.0, -30.0)):
            with self.assertRaises(render_audio_guard.AudioValidationError):
                render_audio_guard.validate(mock.Mock())


if __name__ == "__main__":
    unittest.main()
