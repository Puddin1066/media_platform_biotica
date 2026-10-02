"""Durable R2-backed state store for transactional Satoshi productions."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from media_store import _client, _key


def manifest_key(episode_id: str, production_id: str) -> str:
    return _key(f"studio/{episode_id}/{production_id}/production_manifest.json")


def _bucket() -> str:
    return os.environ["R2_BUCKET"]


def load_manifest(episode_id: str, production_id: str, client=None) -> dict[str, Any] | None:
    client = client or _client()
    key = manifest_key(episode_id, production_id)
    try:
        obj = client.get_object(Bucket=_bucket(), Key=key)
    except Exception as exc:
        response = getattr(exc, "response", {}) or {}
        code = str((response.get("Error") or {}).get("Code") or "")
        if code in {"404", "NoSuchKey", "NotFound"}:
            return None
        raise
    raw = obj["Body"].read()
    data = json.loads(raw.decode("utf-8"))
    if data.get("episode_id") != episode_id or data.get("production_id") != production_id:
        raise RuntimeError("R2 production manifest identity mismatch")
    return data


def save_manifest(manifest: dict[str, Any], client=None) -> dict[str, Any]:
    """Write the canonical manifest and a timestamped immutable snapshot.

    R2 object replacement is atomic from readers' perspective. The immutable
    history object provides recovery/auditability if a writer is interrupted.
    """
    client = client or _client()
    episode_id = manifest["episode_id"]
    production_id = manifest["production_id"]
    manifest = dict(manifest)
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    payload = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    key = manifest_key(episode_id, production_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    history_key = _key(f"studio/{episode_id}/{production_id}/manifests/{stamp}.json")
    kwargs = {
        "Bucket": _bucket(),
        "Body": payload,
        "ContentType": "application/json",
        "Metadata": {"episode_id": episode_id, "production_id": production_id},
    }
    client.put_object(Key=history_key, **kwargs)
    client.put_object(Key=key, **kwargs)
    return {"bucket": _bucket(), "key": key, "history_key": history_key, "bytes": len(payload)}
