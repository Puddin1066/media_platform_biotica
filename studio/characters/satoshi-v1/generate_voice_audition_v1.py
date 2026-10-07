"""Generate five low-cost Satoshi Eleven v4 voice auditions."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import media_store, runway_operation

MANIFEST = ROOT/"studio/characters/satoshi-v1/voice_audition_v1.json"
JOB_ROOT = ROOT/"outputs/satoshi-character/voice-jobs"
WORK_ROOT = ROOT/"outputs/satoshi-character/voice-media"

def require_environment():
    req=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    miss=[x for x in req if not (os.environ.get(x) or "").strip()]
    if miss: raise ValueError("Missing configuration: "+", ".join(miss))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(character_id, asset_id, voice, text):
    raw=json.dumps({"character_id":character_id,"asset_id":asset_id,"voice":voice,"text":text},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]

def archive_for(asset_id):
    def archive(response, job_id, work):
        urls=response.get("output",[])
        if isinstance(urls,dict):
            urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{asset_id}: expected one audio output, got {len(urls)}")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".mp3"
        target=Path(work)/f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as source, target.open("wb") as dest:
            shutil.copyfileobj(source,dest)
        return [media_store.persist(target,f"satoshi/characters/satoshi-v1/audio/voice-auditions/{target.name}")]
    return archive

def main():
    require_environment()
    m=json.loads(MANIFEST.read_text())
    if m["budget"]["hard_phase_cap_credits"]>8 or len(m["voices"])!=5:
        raise ValueError("Voice audition budget/count guard failed")
    results=[]
    for v in m["voices"]:
        body={
            "model":m["model"],
            "promptText":m["script"],
            "voice":{"type":"runway-preset","presetId":v["preset_id"]},
            **m["settings"]
        }
        req={
            "operation":"post_text_to_speech",
            "request_id":rid(m["character_id"],v["asset_id"],v["preset_id"],m["script"]),
            "allow_mutation":True,
            "allow_media_spend":True,
            "estimated_credits":1,
            "body":body
        }
        result=runway_operation.execute(req,archive=archive_for(v["asset_id"]),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=result.get("media",[])
        if result.get("state")!="completed" or len(media)!=1:
            raise RuntimeError(f"{v['asset_id']} failed")
        results.append({"asset_id":v["asset_id"],"preset_id":v["preset_id"],"estimated_credits":result.get("estimated_credits"),"media":media[0]})
    summary={"character_id":m["character_id"],"phase":m["phase"],"state":"completed","estimated_credits":sum(x["estimated_credits"] or 0 for x in results),"auditions":results,"next_action":"human_select_canonical_voice"}
    out=ROOT/"outputs/satoshi-character/voice-audition-v1-result.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__": main()
