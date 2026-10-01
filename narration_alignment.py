"""Measured word timing for an immutable narration master.

Whisper timestamps are observations, not a word-count duration estimate. We
require the transcription to match the approved wording before attaching times
back to that wording. A disagreement blocks assembly rather than silently
changing the script or fabricating timing. Local tools may supply the same words
contract to ``align_words`` without calling another provider.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
import uuid
from pathlib import Path


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def token(value):
    return re.sub(r"[^\w]", "", str(value).casefold(), flags=re.UNICODE)



def _orthographic_token(value):
    # Spoken single-digit numbers and compound-word punctuation can differ in
    # transcription. These are lexical equivalences, never approximate matches.
    digits = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
              "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
    value = token(value)
    return digits.get(value, value)


def match_observations(expected, words):
    """Merge measured words for an exactly equivalent locked compound token.

    A hyphenated word may occupy several observed intervals. Its caption uses
    their full measured span; no timestamps are interpolated and no omitted
    words are filled. Missing or different wording still fails closed.
    """
    observed = [w for w in words if token(w.get("word", ""))]
    matched, cursor = [], 0
    for _, text in expected:
        wanted, joined = _orthographic_token(text), ""
        begin = cursor
        while cursor < len(observed) and cursor - begin < 6:
            joined += _orthographic_token(observed[cursor]["word"])
            cursor += 1
            if joined == wanted:
                matched.append({"word": text, "start": observed[begin]["start"],
                                "end": observed[cursor - 1]["end"]})
                break
            if not wanted.startswith(joined):
                raise ValueError(f"Transcription differs at locked word: {text}")
        else:
            raise ValueError(f"Transcription omits locked word: {text}")
        if joined != wanted:
            raise ValueError(f"Transcription differs at locked word: {text}")
    if cursor != len(observed):
        raise ValueError("Transcription contains words absent from locked script")
    return matched


def align_words(script, words, duration_ms, audio_sha256):
    if not math.isfinite(duration_ms) or duration_ms <= 0:
        raise ValueError("Invalid narration duration")
    expected = [(s["sentence_id"], word) for s in script["script"]
                for word in s["text"].split() if token(word)]
    observed = match_observations(expected, words)
    captions, sentences = [], []
    previous = 0.0
    for (sid, text), measured in zip(expected, observed):
        start, end = float(measured["start"]) * 1000, float(measured["end"]) * 1000
        if not all(math.isfinite(v) for v in (start, end)) or start < previous or end <= start or end > duration_ms + 50:
            raise ValueError("Invalid, overlapping, or out-of-range word timestamps")
        captions.append({"text": " " + text, "startMs": start, "endMs": end,
                         "timestampMs": (start + end) / 2, "confidence": None,
                         "sentence_id": sid})
        if not sentences or sentences[-1]["sentence_id"] != sid:
            sentences.append({"sentence_id": sid, "startMs": start, "endMs": end})
        else:
            sentences[-1]["endMs"] = end
        previous = end
    if not captions:
        raise ValueError("No measured words")
    for i, caption in enumerate(captions):
        caption["pageBreakAfter"] = ((i + 1) % 5 == 0 or i == len(captions) - 1
                                     or captions[i + 1]["sentence_id"] != caption["sentence_id"])
    return {"schema_version": 1, "method": "measured_word_timestamps",
            "audio_sha256": audio_sha256, "duration_ms": duration_ms,
            "captions": captions, "sentences": sentences}


def transcribe(audio, script, key):
    """Use existing OpenAI credentials; never expose the response's audio input."""
    if not key:
        raise ValueError("OpenAI key required for narration alignment")
    boundary = "biotica-" + uuid.uuid4().hex
    fields = {"model": "whisper-1", "response_format": "verbose_json",
              "timestamp_granularities[]": "word", "language": "en",
              "prompt": " ".join(s["text"] for s in script["script"])[-4000:]}
    chunks = []
    for name, value in fields.items():
        chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    data = Path(audio).read_bytes()
    if len(data) > 24_000_000:
        raise ValueError("Narration exceeds bounded transcription upload size")
    chunks.extend([f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="narration.wav"\r\nContent-Type: audio/wav\r\n\r\n'.encode(),
                   data, f'\r\n--{boundary}--\r\n'.encode()])
    request = urllib.request.Request("https://api.openai.com/v1/audio/transcriptions", data=b"".join(chunks),
                                    headers={"Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.loads(response.read(4_000_000))["words"]
