"""Build second library-first pilot: Fruit Ninja / dyslexia."""
import hashlib, json, os, shutil, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store, runway_operation

PRESETS=ROOT/"studio/characters/satoshi-v1/delivery_presets.json"
PUBLIC=ROOT/"remotion/public/fruit-assets"
MANIFEST=ROOT/"remotion/public/library-first-fruit-ninja.json"
JOB_ROOT=ROOT/"outputs/library-first-fruit/voice-jobs"
WORK_ROOT=ROOT/"outputs/library-first-fruit/voice-media"

BEATS=[
 {"id":"hook","mode":"hook","kind":"image",
  "text":"A fruit-slicing phone game improved reading in children with dyslexia. Which sounds like a headline written by a venture capitalist who lost a bet.",
  "asset_key":"satoshi/library/conceptual_broll/SAT-BRL-012.png","asset_name":"software-therapy.png","title":"ORDINARY SOFTWARE, WEIRD RESULT",
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-001.mp3","sfx_name":"reveal.mp3"},
 {"id":"evidence","mode":"evidence","kind":"evidence",
  "text":"In a randomized trial of sixty-four children ages eight to thirteen, five hours of Fruit Ninja training improved reading accuracy, rate, comprehension and rapid naming compared with treatment as usual.",
  "citation":"https://pubmed.ncbi.nlm.nih.gov/34545166/",
  "data":{"study":"Peters et al.","journal":"Scientific Reports","year":"2021","n":"64"},
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-010.mp3","sfx_name":"receipt.mp3"},
 {"id":"mechanism","mode":"evidence","kind":"image",
  "text":"The proposed mechanism was not phonics. It was dynamic visual attention: rapidly tracking targets, inhibiting distractors and processing unpredictable motion.",
  "asset_key":"satoshi/library/conceptual_broll/SAT-BRL-002.png","asset_name":"mechanism.png","title":"PROPOSED MECHANISM",
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-006.mp3","sfx_name":"mechanism.mp3"},
 {"id":"joke","mode":"joke","kind":"video",
  "text":"And adding eye tracking did not make it work better. Sometimes the expensive version is just the same fruit with more hardware.",
  "asset_key":"satoshi/characters/satoshi-v1/silent/SAT-SIL-006.mp4","asset_name":"endpoint-disbelief.mp4","title":"SATOSHI",
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-004.mp3","sfx_name":"joke.mp3"},
 {"id":"correction","mode":"evidence","kind":"correction",
  "text":"That does not make Fruit Ninja a dyslexia treatment. It means a familiar game produced a clinically interesting signal in one randomized study.",
  "data":{"heard":"Fruit Ninja treats dyslexia"},
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-009.mp3","sfx_name":"claim-break.mp3"},
 {"id":"thesis","mode":"landing","kind":"thesis",
  "text":"The business question is whether therapeutic mechanisms are already hiding inside software people willingly use — before anyone turns them into a medical product.",
  "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-007.mp3","sfx_name":"land.mp3"}
]
BED_KEY="satoshi/library/audio/beds/SAT-BED-002.mp3"

def guard():
    req=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    miss=[x for x in req if not (os.environ.get(x) or "").strip()]
    if miss: raise ValueError("Missing config: "+", ".join(miss))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(beat,cfg):
    return hashlib.sha256(json.dumps({"beat":beat["id"],"text":beat["text"],"cfg":cfg},sort_keys=True,separators=(",",":")).encode()).hexdigest()[:32]

def archive_for(asset_id,public_name):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict): urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{asset_id}: expected one output")
        url=urls[0]; suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".mp3"
        target=Path(work)/f"{asset_id}{suffix}"; target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst: shutil.copyfileobj(src,dst)
        shutil.copy2(target,PUBLIC/public_name)
        return [media_store.persist(target,f"satoshi/episodes/library-first-fruit-ninja/audio/{target.name}")]
    return archive

def probe(path):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],text=True).strip())

def main():
    guard(); p=json.loads(PRESETS.read_text()); PUBLIC.mkdir(parents=True,exist_ok=True)
    voices=[]; voice_results=[]
    for i,b in enumerate(BEATS,1):
        cfg=p["delivery_presets"][b["mode"]]
        body={"model":"eleven_v4","promptText":b["text"],"voice":{"type":"runway-preset","presetId":"Clint"},"stability":cfg["stability"],"similarityBoost":cfg["similarityBoost"],"style":cfg["style"],"speed":cfg["speed"],"useSpeakerBoost":cfg["useSpeakerBoost"],"languageCode":"en"}
        req={"operation":"post_text_to_speech","request_id":rid(b,cfg),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,"body":body}
        result=runway_operation.execute(req,archive=archive_for(f"FRUIT-VOX-{i:02d}",f"voice-{i:02d}.mp3"),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=result.get("media",[])
        if result.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"{b['id']} voice failed")
        voices.append(PUBLIC/f"voice-{i:02d}.mp3"); voice_results.append({"beat":b["id"],"media":media[0]})

    concat=ROOT/"outputs/library-first-fruit/concat.txt"; concat.parent.mkdir(parents=True,exist_ok=True)
    concat.write_text("\n".join([f"file '{x.resolve()}'" for x in voices])+"\n")
    narration=PUBLIC/"narration.mp3"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c:a","libmp3lame","-b:a","192k",str(narration)],check=True)
    media_store.fetch(BED_KEY,PUBLIC/"bed.mp3")

    fps=30; frame=0; out=[]
    for b,v in zip(BEATS,voices):
        dur=max(1,round(probe(v)*fps))
        item={"id":b["id"],"from":frame,"duration":dur,"kind":b["kind"],"text":b["text"]}
        for k in ("title","citation","data"):
            if k in b: item[k]=b[k]
        if b.get("asset_key"):
            media_store.fetch(b["asset_key"],PUBLIC/b["asset_name"]); item["asset"]="fruit-assets/"+b["asset_name"]
        if b.get("sfx_key"):
            media_store.fetch(b["sfx_key"],PUBLIC/b["sfx_name"]); item["sfx"]="fruit-assets/"+b["sfx_name"]
        out.append(item); frame+=dur
    MANIFEST.write_text(json.dumps({"fps":fps,"width":1080,"height":1920,"duration_frames":frame,"narration":"fruit-assets/narration.mp3","background_bed":"fruit-assets/bed.mp3","beats":out},indent=2)+"\n")
    result={"state":"ready_to_render","duration_frames":frame,"duration_seconds":frame/fps,"voice_assets":voice_results}
    (ROOT/"outputs/library-first-fruit/build-result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
