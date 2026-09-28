"""Render exact, source-backed overlay cards onto a finished vertical reel.

AI video handles metaphors/comedy. This module handles claims that must stay exact:
numbers, trial names, mechanism labels, product/company relationships and concise
regulatory receipts. Event timing is scaled to the measured reel duration so the
cards follow the locked narration instead of an arbitrary fixed 30-second edit.
"""
from __future__ import annotations

import json
import math
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

CARD_W = 760
CARD_H = 430
OUT_W = 1080
OUT_H = 1920
CARD_X = 56
CARD_Y = 225
NOMINAL_END_SECONDS = 102.0

BG = (18, 24, 35, 238)
PAPER = (244, 240, 229, 248)
INK = (25, 31, 42, 255)
WHITE = (255, 255, 255, 255)
MUTED = (191, 198, 209, 255)
ACCENT = (190, 55, 58, 255)
ACCENT_2 = (41, 111, 161, 255)
GOOD = (65, 126, 86, 255)


def _font(size: int, bold: bool = False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).is_file():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    words = str(text).split()
    rows, row = [], ""
    for word in words:
        probe = (row + " " + word).strip()
        if draw.textbbox((0, 0), probe, font=font)[2] <= max_width:
            row = probe
        else:
            if row:
                rows.append(row)
            row = word
    if row:
        rows.append(row)
    return rows


def _base(title):
    image = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), radius=28,
                        fill=PAPER, outline=(255, 255, 255, 90), width=2)
    d.rectangle((0, 0, 14, CARD_H), fill=ACCENT)
    d.text((42, 28), str(title).upper(), font=_font(31, True), fill=INK)
    d.line((42, 78, CARD_W - 42, 78), fill=(80, 86, 96, 90), width=2)
    return image, d


def _draw_label(event):
    image, d = _base(event.get("title", ""))
    subtitle = event.get("subtitle", "")
    font = _font(38, True)
    y = 130
    for row in _wrap(d, subtitle, font, CARD_W - 90)[:4]:
        d.text((44, y), row, font=font, fill=INK)
        y += 52
    return image


def _draw_stat_compare(event):
    image, d = _base(event.get("title", ""))
    left_value = str(event.get("left_value", ""))
    right_value = str(event.get("right_value", ""))
    d.text((75, 122), left_value, font=_font(72, True), fill=ACCENT)
    d.text((432, 122), right_value, font=_font(72, True), fill=ACCENT_2)
    d.text((75, 210), str(event.get("left_label", "")), font=_font(23, True), fill=INK)
    d.text((432, 210), str(event.get("right_label", "")), font=_font(23, True), fill=INK)
    # Deliberately near-equal bars: exact values stay in typography.
    d.rounded_rectangle((78, 282, 325, 328), radius=12, fill=ACCENT)
    d.rounded_rectangle((435, 282, 689, 328), radius=12, fill=ACCENT_2)
    d.text((76, 354), "PRIMARY ENDPOINT: NO EXCESS SIGNAL", font=_font(24, True), fill=GOOD)
    return image


def _draw_noninferiority(event):
    image, d = _base(event.get("title", ""))
    subtitle = event.get("subtitle", "")
    d.text((50, 120), "BETTER", font=_font(25, True), fill=GOOD)
    d.text((575, 120), "WORSE", font=_font(25, True), fill=ACCENT)
    y = 196
    d.line((85, y, 675, y), fill=INK, width=8)
    d.line((566, y - 42, 566, y + 42), fill=ACCENT, width=6)
    d.text((510, y + 54), "MARGIN", font=_font(20, True), fill=ACCENT)
    d.ellipse((350, y - 19, 388, y + 19), fill=ACCENT_2)
    d.text((300, y - 76), "TRT RESULT", font=_font(21, True), fill=ACCENT_2)
    font = _font(27, True)
    yy = 306
    for row in _wrap(d, subtitle, font, CARD_W - 90)[:2]:
        d.text((45, yy), row, font=font, fill=INK)
        yy += 38
    return image


def _draw_flow(event):
    image, d = _base(event.get("title", ""))
    nodes = event.get("nodes") or []
    if len(nodes) < 2:
        return _draw_label(event)
    x0, x1 = 38, CARD_W - 38
    y = 170
    span = (x1 - x0) / len(nodes)
    centers = []
    for i, node in enumerate(nodes):
        cx = int(x0 + span * (i + 0.5))
        centers.append(cx)
        box = (cx - 76, y - 46, cx + 76, y + 46)
        d.rounded_rectangle(box, radius=18, fill=(231, 235, 238, 255), outline=ACCENT_2, width=3)
        rows = _wrap(d, node, _font(19, True), 132)[:2]
        yy = y - (len(rows) * 12)
        for row in rows:
            tw = d.textbbox((0, 0), row, font=_font(19, True))[2]
            d.text((cx - tw / 2, yy), row, font=_font(19, True), fill=INK)
            yy += 25
        if i:
            d.line((centers[i - 1] + 78, y, cx - 78, y), fill=INK, width=5)
            d.polygon([(cx - 84, y - 8), (cx - 70, y), (cx - 84, y + 8)], fill=INK)
    suppressed = event.get("suppressed_by")
    if suppressed:
        d.text((44, 294), str(suppressed), font=_font(25, True), fill=ACCENT)
        d.text((44, 332), "↓ LH / FSH SIGNAL", font=_font(28, True), fill=ACCENT)
    return image


def _draw_strategy(event):
    image, d = _base(event.get("title", ""))
    for x, label, value, fill in [
        (42, event.get("left_label", ""), event.get("left_value", ""), ACCENT),
        (398, event.get("right_label", ""), event.get("right_value", ""), ACCENT_2),
    ]:
        d.rounded_rectangle((x, 118, x + 320, 352), radius=24,
                            fill=(235, 238, 241, 255), outline=fill, width=4)
        d.text((x + 22, 142), str(label), font=_font(26, True), fill=fill)
        yy = 205
        for row in _wrap(d, value, _font(27, True), 276)[:4]:
            d.text((x + 22, yy), row, font=_font(27, True), fill=INK)
            yy += 38
    return image


def _draw_lineage(event):
    image, d = _base(event.get("title", ""))
    nodes = event.get("nodes") or []
    if not nodes:
        return image
    x = 48
    y = 180
    widths = [180] * len(nodes)
    gap = max(26, (CARD_W - 96 - sum(widths)) // max(1, len(nodes) - 1))
    for i, node in enumerate(nodes):
        d.rounded_rectangle((x, y - 48, x + widths[i], y + 48), radius=18,
                            fill=(236, 239, 242, 255), outline=ACCENT_2, width=3)
        tw = d.textbbox((0, 0), str(node), font=_font(24, True))[2]
        d.text((x + (widths[i] - tw) / 2, y - 15), str(node), font=_font(24, True), fill=INK)
        if i < len(nodes) - 1:
            ax = x + widths[i]
            d.line((ax + 6, y, ax + gap - 8, y), fill=INK, width=5)
            d.polygon([(ax + gap - 8, y - 9), (ax + gap + 7, y), (ax + gap - 8, y + 9)], fill=INK)
        x += widths[i] + gap
    d.text((48, 306), "CORPORATE LINEAGE", font=_font(23, True), fill=MUTED)
    return image


def render_card(event, target):
    kind = event.get("type")
    if kind == "stat_compare":
        image = _draw_stat_compare(event)
    elif kind == "noninferiority":
        image = _draw_noninferiority(event)
    elif kind == "flow":
        image = _draw_flow(event)
    elif kind == "strategy_compare":
        image = _draw_strategy(event)
    elif kind == "lineage":
        image = _draw_lineage(event)
    else:
        image = _draw_label(event)
    image.save(target)


def video_duration(path):
    proc = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nokey=1:noprint_wrappers=1", str(path)
    ], check=True, capture_output=True, text=True, timeout=30)
    return float(proc.stdout.strip())


def apply_graphics(video, spec_path, output):
    video = Path(video)
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))
    events = spec.get("graphics") or []
    if not events:
        raise ValueError("Pilot spec has no deterministic graphics")
    duration = video_duration(video)
    if duration <= 1:
        raise ValueError("Rendered reel is unexpectedly short")
    scale = duration / NOMINAL_END_SECONDS

    with tempfile.TemporaryDirectory(prefix="biotic-graphics-") as tmp:
        tmp = Path(tmp)
        pngs = []
        filters = []
        previous = "[0:v]"
        for i, event in enumerate(events, start=1):
            png = tmp / f"card-{i:02d}.png"
            render_card(event, png)
            pngs.append(png)
            start = max(0.0, float(event["from_seconds"]) * scale)
            end = min(duration, start + float(event["duration_seconds"]) * scale)
            if end <= start:
                continue
            out = f"[v{i}]"
            filters.append(
                f"{previous}[{i}:v]overlay={CARD_X}:{CARD_Y}:"
                f"enable='between(t,{start:.3f},{end:.3f})'{out}"
            )
            previous = out

        cmd = ["ffmpeg", "-nostdin", "-y", "-loglevel", "error", "-i", str(video)]
        for png in pngs:
            cmd += ["-loop", "1", "-i", str(png)]
        cmd += [
            "-filter_complex", ";".join(filters),
            "-map", previous, "-map", "0:a?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart",
            "-t", f"{duration:.3f}", str(output),
        ]
        subprocess.run(cmd, check=True, timeout=1800)
    return Path(output)


def main():
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", required=True)
    p.add_argument("--spec", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    print(apply_graphics(args.video, args.spec, args.output))


if __name__ == "__main__":
    main()
