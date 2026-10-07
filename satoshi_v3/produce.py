from __future__ import annotations
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

REQUIRED = {"episode_id","title","topic","scene","beats","caption","hashtags","sources"}

def validate_episode(path: Path) -> dict:
    data=json.loads(path.read_text(encoding="utf-8"))
    missing=REQUIRED-set(data)
    if missing:
        raise ValueError("v3 episode missing: "+", ".join(sorted(missing)))
    if not isinstance(data["beats"],list) or not data["beats"]:
        raise ValueError("v3 episode requires beats")
    if not isinstance(data["sources"],list) or not data["sources"]:
        raise ValueError("v3 episode requires at least one verified source")
    for i,s in enumerate(data["sources"],1):
        if not str(s.get("title") or "").strip():
            raise ValueError(f"source {i} requires title")
        if not str(s.get("journal_or_source") or "").strip():
            raise ValueError(f"source {i} requires journal_or_source")
        people=s.get("people") or []
        institutions=s.get("institutions") or []
        if not people and not institutions:
            raise ValueError(f"source {i} requires people or institutions")
        if not str(s.get("finding") or "").strip():
            raise ValueError(f"source {i} requires finding")
    for i,b in enumerate(data["beats"],1):
        if not b.get("id") or not b.get("text"):
            raise ValueError(f"beat {i} requires id and text")
        if b.get("kind") not in (None,"host","evidence"):
            raise ValueError(f"beat {i} kind must be host or evidence")
        v=(b.get("visual") or {}).get("type")
        if v not in (None,"host","publication","typography","illustration"):
            raise ValueError(f"beat {i} visual type unsupported by current renderer: {v}")
    return data

def normalize_for_renderer(data: dict) -> dict:
    """Translate v3 audience-facing provenance into the stable v2 renderer contract."""
    out=json.loads(json.dumps(data))
    publications=[]
    for i,s in enumerate(out["sources"],1):
        sid=s.get("id") or f"src{i:02d}"
        people=s.get("people") or []
        institutions=s.get("institutions") or []
        publications.append({
            "id": sid,
            "title": s["title"],
            "authors": ", ".join(people),
            "institutions": institutions,
            "journal": s.get("journal_or_source"),
            "year": s.get("year"),
            "finding": s.get("finding"),
            "source_url": s.get("url"),
        })
        s["id"]=sid
    out["publications"]=publications
    return out

def main():
    p=argparse.ArgumentParser(description="Satoshi v3 production handoff: approved episode only")
    p.add_argument("episode")
    p.add_argument("--publish",action="store_true")
    p.add_argument("--validate-only",action="store_true")
    args=p.parse_args()

    episode_path=Path(args.episode)
    episode=validate_episode(episode_path)
    if args.validate_only:
        print(json.dumps({"status":"valid","episode_id":episode["episode_id"]},indent=2))
        return

    normalized=normalize_for_renderer(episode)
    outdir=Path("outputs/satoshi-v3")/episode["episode_id"]
    outdir.mkdir(parents=True,exist_ok=True)
    normalized_path=outdir/"renderer-episode.json"
    normalized_path.write_text(json.dumps(normalized,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")

    cmd=[sys.executable,"-m","satoshi_v2.produce",str(normalized_path),"--planned","--output","outputs/satoshi-v3"]
    if args.publish:
        cmd.append("--publish")
    subprocess.run(cmd,check=True)

if __name__=="__main__":
    main()
