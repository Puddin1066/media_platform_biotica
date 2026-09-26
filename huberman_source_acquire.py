"""Acquire publicly exposed Huberman Lab transcript text for private analysis.

This module is intentionally narrow:
- only official hubermanlab.com episode URLs from rhetoric_source_manifest.json;
- only transcript text that is exposed on the fetched public episode page;
- raw text is written only to an explicitly supplied private/local directory;
- callers should delete raw snapshots after neutralized mechanics are derived.

It does not authenticate to Huberman Lab Premium, scrape third-party transcript
mirrors, or make raw transcript text available to production prompts.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from rhetoric_source_manifest import load_manifest

USER_AGENT = "BioticaMedia-RhetoricResearch/1.0"
PUBLIC_TRANSCRIPT_MARKERS = (
    "This transcript is currently under human review and may contain errors. The fully reviewed version will be posted as soon as it is available.",
    "This transcript is currently under human review",
    "This transcript version is not in its final form",
)


class VisibleTextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self._chunks: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        elif tag in {"p", "div", "section", "article", "li", "br", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        elif tag in {"p", "div", "section", "article", "li", "h1", "h2", "h3"}:
            self._chunks.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self._chunks.append(data)

    def text(self) -> str:
        text = html.unescape("".join(self._chunks))
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _validate_official_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "www.hubermanlab.com" or not parsed.path.startswith("/episode/"):
        raise ValueError("Only official Huberman Lab episode URLs are allowed")


def fetch_page(url: str, timeout: int = 30) -> str:
    _validate_official_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            raise ValueError("Expected HTML episode page")
        return response.read().decode("utf-8", errors="replace")


def extract_public_transcript(page_html: str) -> tuple[str, str]:
    parser = VisibleTextParser()
    parser.feed(page_html)
    text = parser.text()

    # The public-review disclaimer is the stable transcript boundary on current
    # official episode pages. Newer pages do not necessarily prefix paragraphs
    # with a literal "Andrew Huberman:" speaker label.
    matches = []
    for marker in PUBLIC_TRANSCRIPT_MARKERS:
        pos = text.find(marker)
        if pos >= 0:
            matches.append((pos, marker))
    if not matches:
        raise ValueError("Episode page does not expose a recognized public transcript status")

    marker_pos, marker = min(matches, key=lambda pair: pair[0])
    start = marker_pos + len(marker)
    transcript = text[start:].strip()
    if len(transcript.split()) < 500:
        raise ValueError("Public transcript text appears incomplete")

    return transcript, "public_under_review"


def snapshot_episode(episode: dict, output_dir: Path) -> dict:
    page = fetch_page(episode["url"])
    transcript, status = extract_public_transcript(page)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{episode['id']}.txt"
    path.write_text(transcript, encoding="utf-8")
    sha256 = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
    return {
        "episode_id": episode["id"],
        "url": episode["url"],
        "status": status,
        "word_count": len(transcript.split()),
        "sha256": sha256,
        "private_path": str(path),
    }


def acquire(limit: int, output_dir: Path) -> list[dict]:
    manifest = load_manifest()
    episodes = manifest["episodes"][:limit] if limit else manifest["episodes"]
    results = []
    for episode in episodes:
        try:
            results.append(snapshot_episode(episode, output_dir))
        except Exception as exc:
            results.append({
                "episode_id": episode["id"],
                "url": episode["url"],
                "status": "unavailable",
                "error": str(exc),
            })
    return results


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True, help="Private/local directory; never commit this directory")
    p.add_argument("--limit", type=int, default=0, help="0 means all manifest episodes")
    p.add_argument("--report", help="Optional metadata-only JSON report path")
    args = p.parse_args()

    results = acquire(args.limit, Path(args.output_dir))
    report = {
        "source_policy": "huberman_lab_solo_only",
        "raw_text_policy": "private_transient_only",
        "episodes": results,
    }
    text = json.dumps(report, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
