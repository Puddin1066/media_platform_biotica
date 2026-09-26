"""Reference-corpus contracts for Satoshi writing.

Raw third-party transcripts are intentionally NOT committed to this public repo.
The corpus layer stores source metadata plus derived structural annotations that
can be reviewed, versioned, embedded later, and safely injected into prompts.
"""
from __future__ import annotations

import json
from pathlib import Path

ALLOWED_MODES = {"argumentative", "explanatory", "discovery"}
ALLOWED_FUNCTIONS = {
    "hook", "problem_setup", "mechanism", "evidence", "interpretation",
    "counterargument", "qualification", "practical_implication", "reveal",
    "analogy", "humor", "callback", "conclusion",
}


def validate_source(source):
    required = {"id", "title", "publisher", "source_url", "rights_status", "audience_fit"}
    if not isinstance(source, dict) or not required.issubset(source):
        raise ValueError("Invalid corpus source")
    if not all(isinstance(source[k], str) and source[k].strip()
               for k in ("id", "title", "publisher", "source_url", "rights_status")):
        raise ValueError("Corpus source fields must be non-empty strings")
    fit = source["audience_fit"]
    if not isinstance(fit, list) or not fit or not all(isinstance(x, str) and x.strip() for x in fit):
        raise ValueError("audience_fit must be a non-empty string list")
    return source


def validate_exemplar(item):
    required = {
        "id", "source_id", "mode", "functions", "summary", "mechanics",
        "topic_tags", "rights_status",
    }
    if not isinstance(item, dict) or set(item) != required:
        raise ValueError("Invalid exemplar fields")
    if item["mode"] not in ALLOWED_MODES:
        raise ValueError("Unknown narrative mode")
    functions = item["functions"]
    if not isinstance(functions, list) or not functions or any(f not in ALLOWED_FUNCTIONS for f in functions):
        raise ValueError("Invalid rhetorical functions")
    for key in ("id", "source_id", "summary", "mechanics", "rights_status"):
        if not isinstance(item[key], str) or not item[key].strip():
            raise ValueError(f"{key} must be non-empty")
    tags = item["topic_tags"]
    if not isinstance(tags, list) or not all(isinstance(t, str) and t.strip() for t in tags):
        raise ValueError("topic_tags must be strings")
    return item


def load_sources(path="references/corpus/sources.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("sources.json must contain a list")
    return [validate_source(row) for row in data]


def load_exemplars(root="references/corpus/exemplars"):
    root = Path(root)
    rows = []
    if not root.exists():
        return rows
    for path in sorted(root.glob("*.json")):
        rows.append(validate_exemplar(json.loads(path.read_text(encoding="utf-8"))))
    return rows


def select_exemplars(exemplars, mode, topic_tags=(), limit=3):
    """Deterministic baseline retrieval before embedding retrieval is used."""
    if mode not in ALLOWED_MODES:
        raise ValueError("Unknown narrative mode")
    wanted = {str(t).strip().lower() for t in topic_tags if str(t).strip()}
    scored = []
    for item in exemplars:
        if item["mode"] != mode:
            continue
        tags = {t.lower() for t in item["topic_tags"]}
        scored.append((len(wanted & tags), item["id"], item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [row[2] for row in scored[:max(0, int(limit))]]


def prompt_context(items):
    """Return derived mechanics only; never inject raw third-party transcripts."""
    return [
        {
            "id": item["id"],
            "mode": item["mode"],
            "functions": item["functions"],
            "summary": item["summary"],
            "mechanics": item["mechanics"],
        }
        for item in items
    ]
