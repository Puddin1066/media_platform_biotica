"""Surface the canonical Satoshi Instagram Reel permalink after publication.

A successful live production run is not considered complete for operator review
until the posted Instagram permalink is retrievable. This helper reads the
canonical manifest, resolves the published media ID through the Graph API, writes
a small artifact, exposes a GitHub Actions output, and appends a clickable link to
the Actions job summary.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import instagram


def latest_manifest(root: Path) -> Path:
    manifests = sorted(root.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime)
    if not manifests:
        raise RuntimeError("No canonical Satoshi manifest found")
    return manifests[-1]


def resolve_permalink(manifest: dict) -> tuple[str, str]:
    instagram_packet = manifest.get("instagram") or {}
    result = instagram_packet.get("result") or {}
    publish = result.get("publish") or {}
    media_id = publish.get("media_id")
    if not media_id:
        raise RuntimeError("Manifest does not contain a published Instagram media_id")

    token = os.environ.get("META_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("META_ACCESS_TOKEN is required to resolve Instagram permalink")
    version = os.environ.get("META_GRAPH_VERSION", "v25.0")
    media = instagram.graph("GET", str(media_id), token, {"fields": "id,permalink"}, version)
    permalink = media.get("permalink")
    if not permalink or not str(permalink).startswith("https://www.instagram.com/"):
        raise RuntimeError(f"Instagram did not return a usable permalink for media {media_id}")
    return str(media_id), str(permalink)


def main() -> None:
    root = Path(os.environ.get("SATOSHI_OUTPUT_ROOT", "outputs/canonical-satoshi"))
    manifest_path = latest_manifest(root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    media_id, permalink = resolve_permalink(manifest)

    packet = {
        "status": "published",
        "media_id": media_id,
        "permalink": permalink,
        "manifest": str(manifest_path),
    }
    out = root / "instagram-link.json"
    out.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a", encoding="utf-8") as fh:
            fh.write(f"instagram_url={permalink}\n")
            fh.write(f"instagram_media_id={media_id}\n")

    github_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if github_summary:
        with open(github_summary, "a", encoding="utf-8") as fh:
            fh.write("## Published Satoshi Reel\n\n")
            fh.write(f"[Open the Reel on Instagram]({permalink})\n\n")
            fh.write(f"Media ID: `{media_id}`\n")

    print(permalink)


if __name__ == "__main__":
    main()
