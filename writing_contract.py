"""Deterministic identity for the Satoshi short-writing contract.

Any file that can materially change the researched script or persona mechanics is
part of this digest. The supervisor includes the digest in request identity so a
writing-contract change cannot silently reuse an older draft or rendered reel.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

STATIC_PATHS = (
    "SATOSHI_PERSONA.md",
    "produce.py",
    "satoshi_short.py",
    "narrative_mode.py",
    "reference_corpus.py",
    "monologue_grammar.py",
    "positioning.py",
    "references/corpus/profile.md",
)
GLOB_PATHS = (
    "references/corpus/exemplars/*.json",
)


def contract_paths(root="."):
    root = Path(root)
    paths = []
    for rel in STATIC_PATHS:
        path = root / rel
        if path.is_file():
            paths.append(path)
    for pattern in GLOB_PATHS:
        paths.extend(path for path in root.glob(pattern) if path.is_file())
    return sorted(set(paths), key=lambda p: p.relative_to(root).as_posix())


def digest(root="."):
    root = Path(root)
    paths = contract_paths(root)
    if not paths:
        raise RuntimeError("Satoshi writing contract has no files")
    h = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()
