"""Resolve and persist the public Instagram permalink for a canonical Satoshi publish.

This is the terminal verification stage for the canonical `Produce Satoshi Episode`
workflow. A production publish is not considered complete merely because Meta
returned a media ID: the published media must resolve to a public Instagram
permalink that the operator can open.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import instagram


def _valid_permalink(value):
    try:
        parsed = urlparse(str(value or ""))
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.hostname not in {"instagram.com", "www.instagram.com"}:
        return False
    parts = [part for part in parsed.path.split("/") if part]
    return len(parts) >= 2 and parts[0] in {"reel", "p", "tv"}


def _media_id(packet):
    result = packet.get("result") or {}
    publish = result.get("publish") or {}
    media_id = publish.get("media_id")
    if not media_id:
        raise ValueError("Instagram publish packet is missing result.publish.media_id")
    return str(media_id)


def resolve(packet, token, version="v25.0"):
    """Fetch the just-published media object and require a usable permalink."""
    media_id = _media_id(packet)
    details = instagram.graph(
        "GET", media_id, token,
        {"fields": "id,permalink,media_type,timestamp"}, version,
    )
    permalink = details.get("permalink")
    if not _valid_permalink(permalink):
        raise RuntimeError(
            "Meta reported the Reel as published but did not return a valid Instagram permalink"
        )
    return {
        "media_id": media_id,
        "permalink": permalink,
        "media_type": details.get("media_type"),
        "timestamp": details.get("timestamp"),
        "verified": True,
    }


def enrich_file(path, token=None, version=None):
    path = Path(path)
    if not path.is_file():
        raise ValueError(f"Instagram publish packet not found: {path}")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if packet.get("status") != "published":
        raise ValueError("Instagram packet is not in published state")
    token = token or os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise ValueError("META_ACCESS_TOKEN is required to resolve the Instagram permalink")
    resolved = resolve(packet, token, version or os.environ.get("META_GRAPH_VERSION", "v25.0"))
    packet["permalink"] = resolved["permalink"]
    packet["published_media"] = resolved
    packet.setdefault("result", {})["permalink"] = resolved["permalink"]
    path.write_text(json.dumps(packet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return resolved


def find_publish_packet(root):
    root = Path(root)
    matches = sorted(root.rglob("instagram.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not matches:
        raise ValueError(f"No instagram.json found under {root}")
    return matches[0]


def _append(path, text):
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default="outputs/canonical-satoshi")
    parser.add_argument("--packet", default="")
    args = parser.parse_args()
    try:
        packet = Path(args.packet) if args.packet else find_publish_packet(args.root)
        result = enrich_file(packet)
        permalink = result["permalink"]
        print(permalink)
        _append(os.environ.get("GITHUB_OUTPUT"), f"permalink={permalink}\npacket={packet}\n")
        _append(
            os.environ.get("GITHUB_STEP_SUMMARY"),
            "## Published Satoshi Reel\n\n"
            f"**Instagram:** {permalink}\n\n"
            f"**Media ID:** `{result['media_id']}`\n",
        )
    except (ValueError, RuntimeError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Canonical Instagram permalink verification failed: {exc}\n")


if __name__ == "__main__":
    main()
