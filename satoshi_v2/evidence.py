from __future__ import annotations
import json
from pathlib import Path

def materialize(episode,work):
    """Convert evidence instructions to a render-ready manifest.
    Publication cards are rendered by Remotion from metadata; illustration generation is optional.
    """
    out=[]
    pubs={p.get("id"):p for p in episode.get("publications",[]) if p.get("id")}
    for beat in episode["beats"]:
        visual=dict(beat.get("visual") or {})
        if visual.get("type")=="publication":
            raw=visual.get("publication_ref")
            refs=raw if isinstance(raw,list) else [raw]
            refs=[ref for ref in refs if isinstance(ref,str) and ref.strip()]
            if not refs:
                raise ValueError(f"Publication beat {beat['id']} has no publication_ref")
            unknown=[ref for ref in refs if ref not in pubs]
            if unknown:
                raise ValueError("Unknown publication_ref: "+", ".join(unknown))
            visual["publication"]=pubs[refs[0]]
            visual["publications"]=[pubs[ref] for ref in refs]
            visual["publication_ref"]=refs
        out.append({"beat_id":beat["id"],"visual":visual})
    path=Path(work)/"evidence.json"
    path.write_text(json.dumps(out,indent=2)+"\n")
    return out
