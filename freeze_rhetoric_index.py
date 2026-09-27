"""Build or validate a frozen semantic index for the derived rhetoric mechanics corpus.

Only neutralized mechanics are embedded. Raw transcript text is never read or stored here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from semantic_rhetoric import build_index, load_mechanics


def mechanics_digest(source_dir: Path) -> str:
    rows = load_mechanics(source_dir)
    return hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(index: dict, source_dir: Path) -> None:
    rows = load_mechanics(source_dir)
    episodes = {row["episode_id"] for row in rows}
    assert len(episodes) == 25, len(episodes)
    assert len(rows) > 0
    assert index.get("source_text_included") is False
    assert index.get("creator_voice_imitation") is False
    assert index.get("mechanic_count") == len(rows)
    assert len(index.get("items", [])) == len(rows)
    assert index.get("mechanics_sha256") == mechanics_digest(source_dir)
    dims = index.get("embedding_dimensions")
    assert isinstance(dims, int) and dims > 0
    for item in index["items"]:
        vec = item.get("embedding")
        assert isinstance(vec, list) and len(vec) == dims


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", required=True)
    p.add_argument("--index-path", required=True)
    p.add_argument("--validate-only", action="store_true")
    args = p.parse_args()
    source_dir = Path(args.source_dir)
    index_path = Path(args.index_path)

    if args.validate_only:
        index = json.loads(index_path.read_text(encoding="utf-8"))
        validate(index, source_dir)
        print(f"frozen_index_ok mechanics={index['mechanic_count']} dims={index['embedding_dimensions']}")
        return

    index = build_index(source_dir)
    index["mechanics_sha256"] = mechanics_digest(source_dir)
    index["frozen"] = True
    validate(index, source_dir)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(index, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"frozen_index_written mechanics={index['mechanic_count']} dims={index['embedding_dimensions']} path={index_path}")


if __name__ == "__main__":
    main()
