"""Build final minimum viable Satoshi library tranche for production readiness."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store, runway_operation

MANIFEST=ROOT/"studio/production_readiness_pack_v1.json"
JOB_ROOT=ROOT/"outputs/satoshi-production-ready/jobs"
WORK_ROOT=ROOT/"outputs/satoshi-production-ready/media"

def require_environment():
    req=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    miss=[x for x in req if not (os.environ.get(x) or "").strip()]
    if miss: raise ValueError("Missing config: "+", ".join(miss))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(asset_id, body):
    return hashlib.sha256(json.dumps({"asset_id":asset_id,"body":body},sort_keys=True,separators=(",",":")).encode()).hexdigest()[:32]

def archive_for(asset_id,prefix,default_suffix):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict): urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{asset_id}: expected one output, got {len(urls)}")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or default_suffix
        target=Path(work)/f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=300) as src,target.open("wb") as dst: shutil.copyfileobj(src,dst)
        return [media_store.persist(target,f"{prefix}/{target.name}")]
    return archive

def execute(req,asset_id,prefix,suffix):
    res=runway_operation.execute(req,archive=archive_for(asset_id,prefix,suffix),job_root=JOB_ROOT,work_root=WORK_ROOT)
    media=res.get("media",[])
    if res.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"{asset_id} failed")
    return {"asset_id":asset_id,"estimated_credits":res.get("estimated_credits"),"media":media[0]}

def main():
    require_environment()
    m=json.loads(MANIFEST.read_text())
    if m["budget"]["hard_phase_cap_credits"]>120: raise ValueError("Budget ceiling exceeded")
    results={"reactions":[],"visuals":[],"sound_cues":[],"background_beds":[]}

    for x in m["reactions"]:
        body={"model":m["model_video"],"promptImage":x["source_url"],"promptText":x["prompt"],"ratio":m["video_ratio"],"duration":m["video_duration_seconds"]}
        req={"operation":"post_image_to_video","request_id":rid(x["asset_id"],body),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":20,"body":body}
        item=execute(req,x["asset_id"],"satoshi/characters/satoshi-v1/silent",".mp4"); item["label"]=x["label"]; results["reactions"].append(item)

    for x in m["conceptual_visuals"]:
        body={"model":m["model_image"],"promptText":x["prompt"],"ratio":m["image_ratio"],"outputFormat":"png","outputCount":1}
        req={"operation":"post_text_to_image","request_id":rid(x["asset_id"],body),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,"body":body}
        item=execute(req,x["asset_id"],"satoshi/library/conceptual_broll",".png"); item["label"]=x["label"]; results["visuals"].append(item)

    for group,key,prefix in [(m["sound_cues"],"sound_cues","satoshi/library/audio/sfx"),(m["background_beds"],"background_beds","satoshi/library/audio/beds")]:
        for x in group:
            body={"model":m["sound_model"],"promptText":x["prompt"],"duration":x["duration"],"loop":key=="background_beds"}
            est=float(x["duration"])
            req={"operation":"post_sound_effect","request_id":rid(x["asset_id"],body),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":est,"body":body}
            item=execute(req,x["asset_id"],prefix,".mp3"); item["label"]=x["label"]; item["duration"]=x["duration"]; results[key].append(item)

    total=sum((a["estimated_credits"] or 0) for arr in results.values() for a in arr)
    summary={"state":"completed","phase":m["phase"],"estimated_credits":total,**results,"next_action":"render_first_library_first_episode"}
    out=ROOT/"outputs/satoshi-production-ready/production-readiness-pack-v1-result.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
