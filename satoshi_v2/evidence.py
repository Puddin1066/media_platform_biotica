from __future__ import annotations
import json
from pathlib import Path

def materialize(episode,work):
    """Convert evidence instructions to a render-ready manifest.
    Publication cards are rendered by Remotion from metadata; illustration generation is optional.
    """
    out=[]
    pubs={p.get("id"):p for p in episode.get("publications",[])}
    for beat in episode["beats"]:
        visual=dict(beat.get("visual") or {})
        if visual.get("type")=="publication":
            ref=visual.get("publication_ref")
            if ref not in pubs: raise ValueError(f"Unknown publication_ref {ref}")
            visual["publication"]=pubs[ref]
        out.append({"beat_id":beat["id"],"visual":visual})
    path=Path(work)/"evidence.json"
    path.write_text(json.dumps(out,indent=2)+"\n")
    return out
