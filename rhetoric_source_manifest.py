"""Validate the single-source Huberman rhetoric provenance manifest."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

MANIFEST = Path(__file__).parent / "rhetoric_source_manifest.json"
ALLOWED_BUCKETS = {"mens_health_adjacent", "explanatory_control"}


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_manifest(data)
    return data


def validate_manifest(data):
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported rhetoric source manifest schema")
    if data.get("source_policy") != "huberman_lab_solo_only":
        raise ValueError("Manifest must preserve the single-source Huberman solo policy")
    episodes = data.get("episodes")
    if not isinstance(episodes, list) or not 25 <= len(episodes) <= 50:
        raise ValueError("Initial source cohort must contain 25-50 episodes")

    seen_ids = set()
    seen_urls = set()
    buckets = Counter()
    for episode in episodes:
        required = ("id", "date", "title", "url", "bucket", "focus")
        if not all(key in episode for key in required):
            raise ValueError("Episode entry missing required fields")
        if episode["id"] in seen_ids or episode["url"] in seen_urls:
            raise ValueError("Duplicate episode id or url")
        seen_ids.add(episode["id"])
        seen_urls.add(episode["url"])

        parsed = urlparse(episode["url"])
        if parsed.scheme != "https" or parsed.netloc != "www.hubermanlab.com" or not parsed.path.startswith("/episode/"):
            raise ValueError("Source URLs must be official Huberman Lab episode pages")
        if episode["bucket"] not in ALLOWED_BUCKETS:
            raise ValueError("Unexpected source bucket")
        if not isinstance(episode["focus"], list) or not episode["focus"]:
            raise ValueError("Each episode needs at least one focus tag")
        buckets[episode["bucket"]] += 1

    if min(buckets.values()) < 10:
        raise ValueError("Cohort must include substantial domain-fit and explanatory-control coverage")
    return True


if __name__ == "__main__":
    manifest = load_manifest()
    print(json.dumps({
        "episodes": len(manifest["episodes"]),
        "buckets": dict(Counter(ep["bucket"] for ep in manifest["episodes"])),
        "source_policy": manifest["source_policy"],
    }, indent=2))
