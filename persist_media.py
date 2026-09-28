"""Persist collected Satoshi media to durable object storage.

Safe to run repeatedly: object keys are content-addressed by SHA-256, so retries do
not create duplicate paid media and downstream publishing can use stable URLs.
"""
import argparse
import json
from pathlib import Path

import media_store

MEDIA_EXTENSIONS = {".mp4", ".mp3", ".wav", ".m4a", ".webm"}


def discover(root):
    root = Path(root)
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS and not p.name.endswith(".part")
    )


def persist_roots(roots, prefix="satoshi"):
    results = []
    seen = set()
    for root in roots:
        root_path = Path(root)
        for path in discover(root_path):
            checksum = media_store._sha256(path)
            if checksum in seen:
                continue
            seen.add(checksum)
            key = f"{prefix}/assets/{checksum[:2]}/{checksum}/{path.name}"
            stored = media_store.persist(path, key)
            stored["local_file"] = str(path)
            results.append(stored)
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", action="append", required=True)
    p.add_argument("--prefix", default="satoshi")
    p.add_argument("--manifest", default="outputs/media-manifest.json")
    args = p.parse_args()
    results = persist_roots(args.root, args.prefix)
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({"assets": results}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"persisted": len(results), "manifest": str(manifest)}))


if __name__ == "__main__":
    main()
