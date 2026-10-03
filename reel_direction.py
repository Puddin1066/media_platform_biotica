"""Turn a locked reel into a performance and a cut, not a sentence-by-sentence lecture.

The picture pipeline can already place a card on a sentence. That is not direction.
A reel holds the face on the setup, brings the receipt in on the word it names,
and gets off before the card becomes wallpaper. The spoken script has to be the
same shape or the read and the edit have nothing to cut.
"""
from __future__ import annotations

import re

HOOK_WORDS = 18
BOUNDARY_WORDS = 12
PAYOFF_WORDS = 24
NUMERALS_PER_SENTENCE = 3
OPEN_FACE_MS = 1100
CARD_MS = {"chart": 8000, "typography": 4200, "illustration": 5000, "source": 6000}
BOUNDARY = re.compile(
    r"\b(not proof|not a claim|does not prove|not fda|not approved|no clinical|not clinical)\b",
    re.IGNORECASE,
)


def assert_reel_shape(script):
    """Reject a scoreboard read before voice or picture spend.

    A watchable reel is a hook, one receipt, at most one short boundary, and a
    last line that is the inversion. Caveats live on the source line.
    """
    sentences = script.get("script") or []
    if len(sentences) < 4:
        raise ValueError("A reel needs a hook, a receipt, a turn, and a payoff")
    hook = str(sentences[0].get("text") or "").split()
    if len(hook) > HOOK_WORDS:
        raise ValueError("The hook is a lecture. The first sentence has to land in one breath")
    boundaries = []
    for sentence in sentences:
        text = str(sentence.get("text") or "")
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        if len(numbers) > NUMERALS_PER_SENTENCE:
            raise ValueError("One sentence is a scoreboard. Speak one comparison and put the rest on the chart")
        function = str(sentence.get("function") or "")
        if BOUNDARY.search(text) or "boundary" in function or "disclaimer" in function:
            boundaries.append(sentence)
    if len(boundaries) > 1:
        raise ValueError("The reel can carry one boundary, not a second caution")
    if boundaries and len(str(boundaries[0].get("text") or "").split()) > BOUNDARY_WORDS:
        raise ValueError("The boundary is a spoken disclaimer. Keep it under a breath or move it to the source line")
    payoff = str(sentences[-1].get("text") or "").split()
    if len(payoff) > PAYOFF_WORDS:
        raise ValueError("The payoff is still explaining. End on the inversion")


def compact_performance(prosody):
    """Sentence pace and pauses, short enough to sit inside the speech instruction cap.

    Free-form direction paragraphs are dropped. They blow the instruction budget
    and the voice path used to ignore them anyway.
    """
    if not isinstance(prosody, dict):
        return ""
    bits = []
    for sentence in prosody.get("sentences") or []:
        if not isinstance(sentence, dict):
            continue
        label = str(sentence.get("sentence_id") or "").strip()
        pace = str(sentence.get("pace") or "").strip().lower()
        emphasis = str(sentence.get("emphasis") or "").strip()
        try:
            pause_ms = int(sentence.get("pause_before_ms") or 0)
        except (TypeError, ValueError):
            pause_ms = 0
        piece = []
        if pace in {"brisk", "measured", "deliberate", "slow", "quick"}:
            piece.append(pace)
        if pause_ms >= 200:
            piece.append(f"pause {pause_ms}ms")
        if emphasis and len(emphasis.split()) <= 4:
            piece.append("hit " + emphasis)
        if label and piece:
            bits.append(label + " " + ", ".join(piece))
        if len(" ".join(bits)) > 280:
            break
    return ("Perform: " + "; ".join(bits)) if bits else ""


def _token(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _card_window(shot, words, start, end):
    visual = shot.get("visual_type") or "illustration"
    max_ms = CARD_MS.get(visual, 5000)
    needles = [token for token in (_token(part) for part in re.findall(r"[A-Za-z0-9]+", shot.get("screen_text") or "")) if len(token) > 2]
    hit = None
    for word in words:
        token = _token(word.get("text"))
        if not token:
            continue
        if any(token == needle or (needle.isdigit() and needle in token) or (len(needle) > 3 and token.startswith(needle[:4])) for needle in needles):
            candidate = max(start, float(word["startMs"]) - 80)
            if end - candidate >= 1200:
                hit = candidate
                break
    card_start = start if hit is None else hit
    if end - start > 2200:
        card_start = max(card_start, start + OPEN_FACE_MS)
    card_end = min(end, card_start + max_ms)
    if card_end - card_start < 900:
        card_start = max(start, end - min(max_ms, end - start))
        card_end = end
    return card_start, card_end


def direct_picture(shots, timing):
    """Hold the face on the setup. Cut the card in on its words, then get off.

    Sentence boundaries are not cuts. A 15-second explanation does not keep a
    card up for 15 seconds.
    """
    sentences = {item["sentence_id"]: item for item in timing["sentences"]}
    captions = timing.get("captions") or []
    beats = []
    last = len(shots) - 1
    for index, shot in enumerate(shots):
        ids = shot["sentence_ids"]
        start = float(sentences[ids[0]]["startMs"])
        end = float(sentences[ids[-1]]["endMs"])
        words = [word for word in captions if start - 20 <= float(word["startMs"]) < end]
        card_start, card_end = _card_window(shot, words, start, end)
        if card_start - start >= 600:
            beats.append(_host(f"{shot['shot_id']}-hold", start, card_start))
        duration = card_end - card_start
        visual = shot.get("visual_type") or "illustration"
        if index == 0:
            motion = "push"
        elif visual == "chart":
            motion = "hold"
        elif index == last:
            motion = "crossfade"
        else:
            motion = "slow_zoom" if duration < 5000 else "hold"
        beats.append({
            "beat_id": shot["shot_id"],
            "role": "",
            "text": "",
            "citations": list(shot.get("citations") or []),
            "still": shot.get("still") or "",
            "inset_video": shot.get("inset_video") or "",
            "motion": motion,
            "start_ms": card_start,
            "end_ms": card_end,
            "visual_type": visual,
            "screen_text": shot.get("screen_text") or "",
            "source_label": str(shot.get("source_label") or ""),
            "chart": shot.get("chart"),
            "playback_rate": shot.get("playback_rate") or 1,
        })
        if end - card_end >= 800:
            beats.append(_host(f"{shot['shot_id']}-button", card_end, end))
    return beats


def _host(beat_id, start, end):
    return {
        "beat_id": beat_id, "role": "", "text": "", "citations": [], "still": "",
        "motion": "hold", "start_ms": start, "end_ms": end, "visual_type": "host",
        "screen_text": "", "source_label": "", "chart": None,
    }
