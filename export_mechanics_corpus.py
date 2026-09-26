"""Combine per-episode neutralized mechanics into a durable corpus file.

Input files must be the neutralized *.mechanics.json outputs of huberman_pilot.py.
No source transcript text is accepted or written.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(source_dir: Path) -> dict:
    rows = []
    files = sorted(source_dir.glob("*.mechanics.json"))
    if not files:
        raise ValueError("No neutralized mechanics files found")
    for path in files:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("source_text_included") is not False or doc.get("creator_voice_imitation") is not False:
            raise ValueError(f"Unsafe mechanics document: {path.name}")
        episode_id = doc.get("episode_id")
        mechanics = doc.get("mechanics")
        if not episode_id or not isinstance(mechanics, list):
            raise ValueError(f"Invalid mechanics document: {path.name}")
        for index, item in enumerate(mechanics):
            if set(item) != {"function", "mechanic", "when_to_use", "avoid"}:
                raise ValueError(f"Unexpected mechanic schema: {path.name}")
            rows.append({"episode_id": episode_id, "mechanic_index": index, **item})
    return {
        "schema_version": 1,
        "source_policy": "huberman_lab_solo_only",
        "source_text_included": False,
        "creator_voice_imitation": False,
        "episode_count": len({r["episode_id"] for r in rows}),
        "mechanic_count": len(rows),
        "mechanics": rows,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args()
    result = build(Path(args.source_dir))
    if result["episode_count"] < 25 or result["mechanic_count"] < 100:
        raise SystemExit("Refusing to promote an incomplete rhetoric corpus")
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"episode_count": result["episode_count"], "mechanic_count": result["mechanic_count"]}))


if __name__ == "__main__":
    main()
