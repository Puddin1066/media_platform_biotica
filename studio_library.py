"""Durable, read-only planning and versioned text archive for Satoshi Studio.

Scripts and agent packets stay in repository Git history. R2 media references are
indexed here, but unpublished scripts are never copied to the public media
bucket. No command in this module calls a generation provider or Runway.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

SCHEMA_VERSION = 1
DONE = {"completed", "approved"}
REVIEW = {"needs_review"}


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _checksum(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _media_refs(value):
    """Find verified R2 references inside manifests without guessing media paths."""
    found = {}
    def walk(item):
        if isinstance(item, dict):
            if all(isinstance(item.get(k), str) and item[k] for k in ("key", "sha256", "bucket")):
                ref = {k: item[k] for k in ("bucket", "key", "sha256")}
                for k in ("url", "bytes"):
                    if k in item:
                        ref[k] = item[k]
                found[(ref["bucket"], ref["key"], ref["sha256"])] = ref
            for child in item.values():
                walk(child)
        elif isinstance(item, list):
            for child in item:
                walk(child)
    walk(value)
    return list(found.values())


def capture(root, episode_id, manifest, module, version, outputs, *, legacy=False):
    """Copy successful text outputs into immutable, content-addressed Git files."""
    root = Path(root).resolve()
    workspace = (root / "studio" / "episodes" / episode_id).resolve()
    if workspace.parent != (root / "studio" / "episodes").resolve():
        raise ValueError("Invalid episode workspace")
    catalog_path = workspace / "library.json"
    catalog = _read(catalog_path, {"schema_version": SCHEMA_VERSION, "episode_id": episode_id, "records": []})
    if catalog.get("episode_id") != episode_id:
        raise ValueError("Mismatched episode library")
    registry = {m["id"]: m for m in _read(root / "studio" / "modules.json", {"modules": []})["modules"]}
    dependencies = {}
    for dep in registry.get(module, {}).get("requires", []):
        state = manifest["modules"].get(dep, {})
        dependencies[dep] = {"version": state.get("version", 0), "status": state.get("status")}
    request_path = root / manifest["request_path"]
    request_sha = _checksum(request_path) if request_path.is_file() and not legacy else None
    records = list(catalog["records"])
    for output in outputs:
        path = (root / output).resolve()
        if not path.is_relative_to(workspace / "artifacts") or not path.is_file():
            raise ValueError(f"Output is missing or outside episode artifacts: {output}")
        if path.suffix.lower() not in {".json", ".txt", ".md"}:
            raise ValueError(f"Unexpected binary output in Git artifact list: {output}")
        sha = _checksum(path)
        object_path = workspace / "library" / "objects" / sha[:2] / (sha + path.suffix.lower())
        if object_path.exists():
            if _checksum(object_path) != sha:
                raise ValueError(f"Archived artifact changed: {object_path}")
        else:
            object_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, object_path)
        media = _media_refs(_read(path, {}) if path.suffix.lower() == ".json" else {})
        record = {
            "id": f"{module}:v{version}:{sha}",
            "module": module,
            "version": version,
            "source_path": str(path.relative_to(root)),
            "snapshot_path": str(object_path.relative_to(root)),
            "sha256": sha,
            "bytes": path.stat().st_size,
            "request_sha256": request_sha,
            "provenance": "current_snapshot_only" if legacy else "captured_at_generation",
            "depends_on": dependencies,
            "media_refs": media,
        }
        if not any(r["id"] == record["id"] and r["source_path"] == record["source_path"] for r in records):
            records.append(record)
    catalog["records"] = records
    _write(catalog_path, catalog)
    return records


def plan(root):
    """Report inventory and next reversible stage, with no provider calls."""
    root = Path(root)
    registry = _read(root / "studio" / "modules.json", {"modules": []})["modules"]
    episodes = []
    for workspace in sorted((root / "studio" / "episodes").glob("*")):
        path = workspace / "episode_manifest.json"
        if not path.is_file():
            continue
        manifest = _read(path, {})
        if not manifest.get("episode_id"):
            continue
        states = manifest.get("modules", {})
        catalog = _read(workspace / "library.json", {"records": []})
        request = _read(root / manifest.get("request_path", ""), {})
        ready, review, missing = [], [], []
        for entry in registry:
            module = entry["id"]
            state = states.get(module, {})
            status = state.get("status", "not_ready")
            if status in REVIEW:
                review.append(module)
            elif status in DONE:
                continue
            elif all(states.get(dep, {}).get("status") in DONE for dep in entry.get("requires", [])):
                ready.append(module)
            else:
                missing.append(module)
        episodes.append({
            "episode_id": manifest["episode_id"],
            "title": manifest.get("title"),
            "request_path": manifest.get("request_path"),
            "modules": {m["id"]: states.get(m["id"], {}).get("status", "not_ready") for m in registry},
            "archived_records": len(catalog.get("records", [])),
            "legacy_records": sum(record.get("provenance") == "current_snapshot_only" for record in catalog.get("records", [])),
            "ready_to_dispatch": ready,
            "requires_review": review,
            "waiting_for_dependencies": missing,
            "runway_credit_cap": request.get("production", {}).get("max_runway_credits"),
            "runway_credits_available": None,
            "media_spend_authorized": False,
        })
    return {"schema_version": SCHEMA_VERSION, "episodes": episodes}


def refresh_index(root):
    result = plan(root)
    _write(Path(root) / "studio" / "library_index.json", result)
    return result


def backfill(root):
    """Archive current episode artifacts. Earlier Git revisions need separate import."""
    root = Path(root)
    for workspace in sorted((root / "studio" / "episodes").glob("*")):
        path = workspace / "episode_manifest.json"
        if not path.is_file():
            continue
        manifest = _read(path, {})
        for module, state in manifest.get("modules", {}).items():
            outputs = [output for output in state.get("outputs", []) if (root / output).is_file()]
            if outputs and int(state.get("version") or 0):
                capture(root, manifest["episode_id"], manifest, module, int(state["version"]), outputs, legacy=True)
    return refresh_index(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "backfill"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    result = backfill(args.root) if args.command == "backfill" else plan(args.root)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
