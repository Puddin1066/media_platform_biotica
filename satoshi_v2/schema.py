from __future__ import annotations
import json, hashlib
from pathlib import Path

REQUIRED_TOP = {"episode_id","title","topic","scene","beats"}

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False)

def digest(value):
    raw = canonical(value).encode("utf-8") if not isinstance(value,(bytes,bytearray)) else value
    return hashlib.sha256(raw).hexdigest()

def load_episode(path):
    data=json.loads(Path(path).read_text(encoding="utf-8"))
    missing=REQUIRED_TOP-set(data)
    if missing: raise ValueError("Episode missing: "+", ".join(sorted(missing)))
    if not isinstance(data["beats"],list) or not data["beats"]:
        raise ValueError("Episode requires beats")
    ids=[]
    for i,b in enumerate(data["beats"],1):
        if not b.get("id") or not b.get("text"):
            raise ValueError(f"Beat {i} requires id and text")
        if b["id"] in ids: raise ValueError("Beat IDs must be unique")
        ids.append(b["id"])
        b.setdefault("kind","host")
        b.setdefault("visual",{"type":"host"})
    scene=data["scene"]
    for field in ("environment","wardrobe","framing"):
        if not str(scene.get(field) or "").strip():
            raise ValueError("Scene missing "+field)
    return data
