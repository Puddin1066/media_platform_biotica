from __future__ import annotations
import json
from pathlib import Path

def materialize(episode,work):
    """Convert evidence instructions to a render-ready manifest.

    Publication visuals may cite one publication ID or a list. The first becomes
    the primary on-screen receipt; the full resolved set remains attached as
    supporting_publications for future renderers/captions.
    """
    out=[]
    pubs={p.get("id"):p for p in episode.get("publications",[]) if p.get("id")}
    for beat in episode["beats"]:
        visual=dict(beat.get("visual") or {})
        if visual.get("type")=="publication":
            raw=visual.get("publication_ref")
            refs=raw if isinstance(raw,list) else [raw]
            refs=[str(x) for x in refs if x]
            if not refs:
                raise ValueError(f"Publication beat {beat['id']} has no publication_ref")
            unknown=[ref for ref in refs if ref not in pubs]
            if unknown:
                raise ValueError("Unknown publication_ref(s): "+", ".join(unknown))
            visual["publication_ref"]=refs[0]
            visual["publication"]=pubs[refs[0]]
            visual["supporting_publications"]=[pubs[ref] for ref in refs]
        out.append({"beat_id":beat["id"],"visual":visual})
    path=Path(work)/"evidence.json"
    path.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n")
    return out
