"""Run a controlled Huberman rhetoric corpus build: acquire public source text, derive neutralized mechanics, delete raw text."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import huberman_mechanics_extract as hme
import huberman_source_acquire as hsa
from rhetoric_source_manifest import load_manifest

MAX_EPISODES = 25


def run(limit: int, output_dir: Path) -> dict:
    if not 1 <= limit <= MAX_EPISODES:
        raise ValueError(f"Pilot limit must be between 1 and {MAX_EPISODES} episodes")
    manifest = load_manifest()
    selected = manifest["episodes"][:limit]
    if len(selected) != limit:
        raise ValueError(f"Manifest contains only {len(selected)} selectable episodes")
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    with tempfile.TemporaryDirectory(prefix="biotica-huberman-") as tmp:
        private_dir = Path(tmp)
        for episode in selected:
            try:
                acquisition = hsa.snapshot_episode(episode, private_dir)
                source_path = Path(acquisition["private_path"])
                derived = hme.derive(source_path, episode["id"])
                out_path = output_dir / f"{episode['id']}.mechanics.json"
                out_path.write_text(json.dumps(derived, indent=2) + "\n", encoding="utf-8")
                results.append({
                    "episode_id": episode["id"],
                    "url": episode["url"],
                    "acquisition_status": acquisition["status"],
                    "word_count": acquisition["word_count"],
                    "source_sha256": acquisition["sha256"],
                    "mechanics_file": out_path.name,
                    "mechanics_count": len(derived["mechanics"]),
                    "raw_source_retained": False,
                    "status": "success",
                })
            except Exception as exc:
                results.append({
                    "episode_id": episode["id"],
                    "url": episode["url"],
                    "status": "failed",
                    "error": str(exc),
                    "raw_source_retained": False,
                })
        # TemporaryDirectory cleanup removes every raw transcript snapshot.

    report = {
        "schema_version": 1,
        "source_policy": "huberman_lab_solo_only",
        "pilot_limit": limit,
        "raw_source_policy": "transient_deleted_before_output",
        "episodes": results,
    }
    (output_dir / "pilot-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--limit", type=int, default=1)
    p.add_argument("--output-dir", default="artifacts/huberman-pilot")
    args = p.parse_args()
    report = run(args.limit, Path(args.output_dir))
    print(json.dumps(report, indent=2))
    failures = [row for row in report["episodes"] if row.get("status") != "success"]
    if failures:
        print(f"Pilot failed for {len(failures)} episode(s)", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
