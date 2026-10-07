from __future__ import annotations
import argparse, json, subprocess, sys
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
    return data

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

    cmd=[sys.executable,"-m","satoshi_v2.produce",str(episode_path),"--planned","--output","outputs/satoshi-v3"]
    if args.publish:
        cmd.append("--publish")
    subprocess.run(cmd,check=True)

if __name__=="__main__":
    main()
