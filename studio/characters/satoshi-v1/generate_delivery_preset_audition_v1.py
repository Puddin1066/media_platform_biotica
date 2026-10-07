"""Generate four Clint delivery-preset samples for Satoshi."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store, runway_operation
PRESETS=ROOT/"studio/characters/satoshi-v1/delivery_presets.json"
MANIFEST=ROOT/"studio/characters/satoshi-v1/delivery_preset_audition_v1.json"
JOB_ROOT=ROOT/"outputs/satoshi-character/delivery-jobs"
WORK_ROOT=ROOT/"outputs/satoshi-character/delivery-media"

def require_environment():
    required=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing=[x for x in required if not (os.environ.get(x) or "").strip()]
    if missing: raise ValueError("Missing configuration: "+", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(asset_id,mode,text,settings):
    raw=json.dumps({"asset_id":asset_id,"mode":mode,"text":text,"settings":settings},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]

def archive_for(asset_id):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict):
            urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{asset_id}: expected one output")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".mp3"
        target=Path(work)/f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as source, target.open("wb") as dest:
            shutil.copyfileobj(source,dest)
        return [media_store.persist(target,f"satoshi/characters/satoshi-v1/audio/delivery-presets/{target.name}")]
    return archive

def main():
    require_environment()
    p=json.loads(PRESETS.read_text())
    m=json.loads(MANIFEST.read_text())
    if p["preset_id"]!="Clint" or m["voice"]["presetId"]!="Clint": raise ValueError("Canonical voice mismatch")
    if m["budget"]["hard_phase_cap_credits"]>6 or len(m["samples"])!=4: raise ValueError("Budget/count guard")
    results=[]
    for s in m["samples"]:
        cfg=p["delivery_presets"][s["mode"]]
        body={
            "model":m["model"],
            "promptText":s["text"],
            "voice":m["voice"],
            "stability":cfg["stability"],
            "similarityBoost":cfg["similarityBoost"],
            "style":cfg["style"],
            "speed":cfg["speed"],
            "useSpeakerBoost":cfg["useSpeakerBoost"],
            "languageCode":"en"
        }
        req={"operation":"post_text_to_speech","request_id":rid(s["asset_id"],s["mode"],s["text"],cfg),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,"body":body}
        result=runway_operation.execute(req,archive=archive_for(s["asset_id"]),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=result.get("media",[])
        if result.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"{s['asset_id']} failed")
        results.append({"asset_id":s["asset_id"],"mode":s["mode"],"media":media[0],"estimated_credits":result.get("estimated_credits")})
    summary={"character_id":m["character_id"],"phase":m["phase"],"state":"completed","estimated_credits":sum(x["estimated_credits"] or 0 for x in results),"samples":results,"next_action":"human_prosody_review_then_use_as_canonical_delivery_presets"}
    out=ROOT/"outputs/satoshi-character/delivery-preset-audition-v1-result.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))
if __name__=="__main__": main()
