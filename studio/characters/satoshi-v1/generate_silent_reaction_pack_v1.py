"""Generate the first three reusable silent Satoshi reaction clips."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import media_store
import runway_operation

MANIFEST = ROOT / "studio/characters/satoshi-v1/silent_reaction_pack_v1.json"
JOB_ROOT = ROOT / "outputs/satoshi-character/silent-jobs"
WORK_ROOT = ROOT / "outputs/satoshi-character/silent-media"

def require_environment():
    required = ["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing = [x for x in required if not (os.environ.get(x) or "").strip()]
    if missing:
        raise ValueError("Refusing paid generation; missing configuration: " + ", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED") != "true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(character_id, asset_id, source_url, prompt):
    raw = json.dumps({"character_id":character_id,"asset_id":asset_id,"source_url":source_url,"prompt":prompt},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]

def archive_for(asset_id):
    def archive(response, job_id, work):
        urls = response.get("output", [])
        if isinstance(urls, dict):
            urls = [u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls = [u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls) != 1:
            raise RuntimeError(f"{asset_id}: expected exactly one video output, got {len(urls)}")
        url = urls[0]
        suffix = Path(urllib.parse.urlsplit(url).path).suffix or ".mp4"
        target = Path(work) / f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as source, target.open("wb") as dest:
            shutil.copyfileobj(source,dest)
        return [media_store.persist(target, f"satoshi/characters/satoshi-v1/silent/{target.name}")]
    return archive

def main():
    require_environment()
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("identity_status") != "locked" or manifest.get("canonical_asset_id") != "SAT-CAST-004":
        raise ValueError("Silent pack requires locked SAT-CAST-004 identity")
    if manifest["budget"]["estimated_credits"] != 60 or manifest["budget"]["hard_phase_cap_credits"] != 60:
        raise ValueError("Silent pack is locked to a 60-credit ceiling")
    if len(manifest.get("clips",[])) != 3:
        raise ValueError("Silent pack v1 requires exactly three clips")
    results=[]
    for clip in manifest["clips"]:
        request={
            "operation":"post_image_to_video",
            "request_id":rid(manifest["character_id"],clip["asset_id"],clip["source_url"],clip["prompt"]),
            "allow_mutation":True,
            "allow_media_spend":True,
            "estimated_credits":20,
            "body":{
                "model":manifest["model"],
                "promptImage":clip["source_url"],
                "promptText":clip["prompt"],
                "ratio":manifest["ratio"],
                "duration":manifest["duration_seconds"]
            }
        }
        result=runway_operation.execute(request,archive=archive_for(clip["asset_id"]),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=result.get("media",[])
        if result.get("state")!="completed" or len(media)!=1:
            raise RuntimeError(f"{clip['asset_id']} did not complete")
        results.append({"asset_id":clip["asset_id"],"label":clip["label"],"source_reference":clip["source_reference"],"estimated_credits":result.get("estimated_credits"),"media":media[0]})
    summary={"character_id":manifest["character_id"],"phase":manifest["phase"],"state":"completed","estimated_credits":sum(x["estimated_credits"] or 0 for x in results),"clips":results,"next_action":"human_review_before_more_silent_or_speaking_assets"}
    out=ROOT/"outputs/satoshi-character/silent-reaction-pack-v1-result.json"
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps(summary,indent=2))

if __name__=="__main__":
    main()
