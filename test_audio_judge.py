import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audio_judge
import satoshi_editorial_audio_pipeline as pipeline


class AudioJudgeTests(unittest.TestCase):
    def test_extract_json_accepts_wrapped_json(self):
        out = audio_judge._extract_json('result: {"selected":"b","takes":{"a":{},"b":{},"c":{}}}')
        self.assertEqual(out["selected"], "b")

    def test_judge_requires_three_takes(self):
        with self.assertRaises(ValueError):
            audio_judge.judge({"a": Path("a.wav")}, {}, {}, "key")

    def test_mechanical_validate_requires_nonempty_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = {}
            for name in ("a", "b", "c"):
                path = Path(tmp) / f"{name}.wav"
                path.write_bytes(b"x" * 2048)
                paths[name] = path
            with patch.object(pipeline.base, "duration", return_value=30.0):
                rows = pipeline.mechanical_validate(paths)
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(row["valid"] for row in rows))

    def test_judge_rejects_invalid_selected_take(self):
        with tempfile.TemporaryDirectory() as tmp:
            takes = {}
            for name in ("a", "b", "c"):
                path = Path(tmp) / f"{name}.wav"
                path.write_bytes(b"RIFFdata")
                takes[name] = path

            class Response:
                def __enter__(self):
                    return self
                def __exit__(self, *args):
                    return False
                def read(self, *_args):
                    return b'{"choices":[{"message":{"content":"{\\"selected\\":\\"z\\",\\"takes\\":{\\"a\\":{},\\"b\\":{},\\"c\\":{}}}"}}]}'

            with patch.object(audio_judge.urllib.request, "urlopen", return_value=Response()):
                with self.assertRaises(ValueError):
                    audio_judge.judge(takes, {"script": []}, {"sentences": []}, "key")


if __name__ == "__main__":
    unittest.main()
