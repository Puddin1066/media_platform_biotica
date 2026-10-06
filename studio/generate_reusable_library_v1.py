"""Generate reusable Satoshi environment/B-roll stills and short sound-design cues."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store, runway_operation
VIS=ROOT/"studio/reusable_visual_library_v1.json"
SFX=ROOT/"studio/audio_brand_v1.json"
JOB_ROOT=ROOT/"outputs/satoshi-library/jobs"
WORK_ROOT=ROOT/"outputs/satoshi-library/media"

def require_environment():
    req=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing=[x for x in req if not (os.environ.get(x) or "").strip()]
    if missing: raise ValueError("Missing config: "+", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(asset_id,payload):
    return hashlib.sha256(json.dumps({"asset_id":asset_id,"payload":payload},sort_keys=True,separators=(",",":")).encode()).hexdigest()[:32]

def archive_for(asset_id,prefix,default_suffix):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict): urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{asset_id}: expected one output, got {len(urls)}")
        url=urls[0]; suffix=Path(urllib.parse.urlsplit(url).path).suffix or default_suffix
        target=Path(work)/f"{asset_id}{suffix}"; target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=240) as src,target.open("wb") as dst: shutil.copyfileobj(src,dst)
        return [media_store.persist(target,f"{prefix}/{target.name}")]
    return archive

def main():
    require_environment()
    vis=json.loads(VIS.read_text()); sfx=json.loads(SFX.read_text())
    if len(vis["assets"])!=12 or vis["budget"]["hard_phase_cap_credits"]>14: raise ValueError("Visual guard failed")
    if len(sfx["assets"])!=8 or sfx["budget"]["hard_phase_cap_credits"]>18: raise ValueError("SFX guard failed")
    vr=[]
    for a in vis["assets"]:
        body={"model":vis["model"],"promptText":a["prompt"],"ratio":vis["ratio"],"outputFormat":"png","outputCount":1}
        req={"operation":"post_text_to_image","request_id":rid(a["asset_id"],body),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,"body":body}
        res=runway_operation.execute(req,archive=archive_for(a["asset_id"],f"satoshi/library/{a['category']}",".png"),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=res.get("media",[])
        if res.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"{a['asset_id']} failed")
        vr.append({"asset_id":a["asset_id"],"category":a["category"],"label":a["label"],"media":media[0],"estimated_credits":res.get("estimated_credits")})
    sr=[]
    for a in sfx["assets"]:
        body={"model":sfx["model"],"promptText":a["prompt"],"duration":a["duration"],"loop":False}
        est=max(1,float(a["duration"]))
        req={"operation":"post_sound_effect","request_id":rid(a["asset_id"],body),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":est,"body":body}
        res=runway_operation.execute(req,archive=archive_for(a["asset_id"],"satoshi/library/audio/sfx",".mp3"),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=res.get("media",[])
        if res.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"{a['asset_id']} failed")
        sr.append({"asset_id":a["asset_id"],"label":a["label"],"duration":a["duration"],"media":media[0],"estimated_credits":res.get("estimated_credits")})
    summary={"state":"completed","visual_assets":vr,"sound_assets":sr,"estimated_credits":sum((x["estimated_credits"] or 0) for x in vr+sr),"next_action":"index_assets_and_wire_remotion_resolver"}
    out=ROOT/"outputs/satoshi-library/reusable-library-v1-result.json"; out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n"); print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
