"""Run the real-evidence rhetoric benchmark with hardened writer/judge and optional frozen embeddings."""
from __future__ import annotations

import json
import os
from pathlib import Path

import real_rhetoric_benchmark as benchmark
from robust_rhetoric_judge import judge
from robust_rhetoric_writer import response_text


def frozen_build_index(_source_dir: Path) -> dict:
    path = os.environ.get("RHETORIC_INDEX_PATH")
    if not path:
        return benchmark._original_build_index(_source_dir)
    index_path = Path(path)
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("source_text_included") is not False or index.get("creator_voice_imitation") is not False:
        raise ValueError("Unsafe frozen rhetoric index")
    if index.get("mechanic_count") != 227 or len(index.get("items", [])) != 227:
        raise ValueError("Frozen rhetoric index count mismatch")
    return index


if __name__ == "__main__":
    benchmark._judge = judge
    benchmark._response_text = response_text
    benchmark._original_build_index = benchmark.build_index
    if os.environ.get("RHETORIC_INDEX_PATH"):
        benchmark.build_index = frozen_build_index
    benchmark.main()
