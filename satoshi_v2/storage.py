from __future__ import annotations
from pathlib import Path
import media_store

def persist(path, episode_id, kind, name=None):
    p=Path(path)
    key=f"satoshi-v2/{episode_id}/{kind}/{name or p.name}"
    return media_store.persist(p,key)

def fetch(record, destination):
    return media_store.fetch(record["key"], destination)
