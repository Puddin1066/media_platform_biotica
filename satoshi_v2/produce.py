from __future__ import annotations
import argparse, json, shutil, subprocess
from pathlib import Path

from satoshi_v2.schema import load_episode, digest
from satoshi_v2 import runway
from satoshi_v2.evidence import materialize
from satoshi_v2.storage import persist
from satoshi_v2.planner import plan

ROOT=Path(__file__).resolve().parents[1]
REMOTION=ROOT/"remotion"
PUBLIC=REMOTION/"public"/"satoshi-v2"
RENDER_JSON=PUBLIC/"render.json"

def copy_asset(src,name):
    PUBLIC.mkdir(parents=True,exist_ok=True)
    dst=PUBLIC/name
    shutil.copyfile(src,dst)
    return "satoshi-v2/"+name

def concat_audio(parts,target):
    listing=target.with_suffix(".txt")
    listing.write_text("".join("file '"+Path(p).resolve().as_posix()+"'\n" for p in parts))
    subprocess.run(["ffmpeg","-nostdin","-y","-v","error","-f","concat","-safe","0",
                    "-i",str(listing),"-c:a","aac","-b:a","192k",str(target)],check=True,timeout=300)
    return target

def make_render_manifest(episode,work):
    scene_path,scene_record=runway.scene_image(episode,work)
    scene_public=copy_asset(scene_path,"scene.png")
    evidence=materialize(episode,work)
    evidence_by={x["beat_id"]:x["visual"] for x in evidence}
    fps=30; frame=0; audio_parts=[]; beats=[]
    for beat in episode["beats"]:
        audio,_=runway.clint_tts(episode,beat,work)
        audio_parts.append(audio)
        seconds=runway.duration(audio)
        frames=max(1,round(seconds*fps))
        row={"id":beat["id"],"text":beat["text"],"kind":beat.get("kind","host"),
             "from":frame,"duration":frames,"visual":evidence_by[beat["id"]]}
        if row["kind"]=="host":
            host,host_record,visible_seconds=runway.act_two(episode,beat,scene_path,audio,work)
            row["host_src"]=copy_asset(host,"host-"+beat["id"]+".mp4")
            row["host_record"]=host_record
            row["host_duration"]=max(1,round(visible_seconds*fps))
        beats.append(row); frame += frames
    narration=Path(work)/"narration.m4a"
    concat_audio(audio_parts,narration)
    voice_public=copy_asset(narration,"narration.m4a")
    manifest={"schema_version":1,"episode_id":episode["episode_id"],"title":episode["title"],
              "fps":fps,"width":1080,"height":1920,"duration_frames":frame,
              "voice":voice_public,"scene":scene_public,"scene_record":scene_record,"beats":beats}
    RENDER_JSON.write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    return manifest

def render(episode,work):
    manifest=make_render_manifest(episode,work)
    subprocess.run(["npm","run","typecheck"],cwd=REMOTION,check=True,timeout=300)
    out=REMOTION/"out"/(episode["episode_id"]+".mp4")
    out.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(["npx","remotion","render","src/index.ts","SatoshiV2",str(out.relative_to(REMOTION))],
                   cwd=REMOTION,check=True,timeout=1800)
    if not out.is_file() or out.stat().st_size<=0: raise RuntimeError("v2 render missing")
    record=persist(out,episode["episode_id"],"final",out.name)
    media_manifest=Path(work)/"media-manifest.json"
    media_manifest.write_text(json.dumps({"assets":[{**record,"local_file":str(out)}]},indent=2)+"\n")
    return out,record,media_manifest,manifest

def publish(video,manifest_path,request_path,work):
    output=Path(work)/"instagram-publish.json"
    cmd=["python","publish_satoshi_instagram.py","--video",str(video),"--manifest",str(manifest_path),
         "--request",str(request_path),"--ledger",str(Path(work)/"instagram.sqlite"),
         "--live","--reviewer","satoshi-v2","--output",str(output)]
    subprocess.run(cmd,cwd=ROOT,check=True,timeout=600)
    return json.loads(output.read_text())

def main():
    p=argparse.ArgumentParser(description="One-command Satoshi Reel producer v2")
    p.add_argument("request")
    p.add_argument("--publish",action="store_true")
    p.add_argument("--planned",action="store_true")
    p.add_argument("--output",default="outputs/satoshi-v2")
    p.add_argument("--validate-only",action="store_true")
    args=p.parse_args()

    request_path=Path(args.request)
    raw=json.loads(request_path.read_text())
    outroot=Path(args.output); outroot.mkdir(parents=True,exist_ok=True)

    if args.planned or all(k in raw for k in ("episode_id","title","topic","scene","beats")):
        episode=load_episode(request_path)
        episode_path=request_path
    else:
        episode_path=outroot/"episode.json"
        plan(raw,episode_path)
        episode=load_episode(episode_path)

    if args.validate_only:
        subprocess.run(["npm","run","typecheck"],cwd=REMOTION,check=True,timeout=300)
        print(json.dumps({"status":"valid","episode_id":episode["episode_id"],"episode_sha256":digest(episode)},indent=2))
        return

    work=outroot/episode["episode_id"]; work.mkdir(parents=True,exist_ok=True)
    (work/"episode.json").write_text(json.dumps(episode,indent=2,ensure_ascii=False)+"\n")
    video,record,media_manifest,_=render(episode,work)
    result={"status":"rendered","episode_id":episode["episode_id"],"video":record,
            "episode_sha256":digest(episode),"render_manifest":str(RENDER_JSON)}
    if args.publish:
        result["publish"]=publish(video,media_manifest,episode_path,work)
        result["status"]="published"
    (work/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
