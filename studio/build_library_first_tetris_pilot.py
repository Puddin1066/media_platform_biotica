"""Build a fully library-first Tetris pilot and render-ready Remotion manifest."""
import hashlib, json, os, shutil, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import media_store, runway_operation

PRESETS=ROOT/"studio/characters/satoshi-v1/delivery_presets.json"
PUBLIC=ROOT/"remotion/public/pilot-assets"
MANIFEST=ROOT/"remotion/public/library-first-pilot.json"
JOB_ROOT=ROOT/"outputs/library-first-pilot/voice-jobs"
WORK_ROOT=ROOT/"outputs/library-first-pilot/voice-media"

BEATS=[
    {
      "id":"hook","mode":"hook","kind":"image",
      "text":"Digital health spent years trying to put medicine inside video games. Tetris may have accidentally gone the other direction.",
      "asset_key":"satoshi/library/conceptual_broll/SAT-BRL-004.png",
      "asset_name":"hook.png","title":"THE WEIRD PART",
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-001.mp3","sfx_name":"evidence-reveal.mp3"
    },
    {
      "id":"evidence","mode":"evidence","kind":"evidence",
      "text":"In a randomized emergency-department study after motor-vehicle trauma, a reminder plus about twenty minutes of Tetris was associated with fewer intrusive memories over the following week.",
      "citation":"https://pubmed.ncbi.nlm.nih.gov/28348380/",
      "data":{"study":"Iyadurai et al.","journal":"Molecular Psychiatry","year":"2018","n":"71"},
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-010.mp3","sfx_name":"receipt-drop.mp3"
    },
    {
      "id":"mechanism","mode":"evidence","kind":"image",
      "text":"The proposed mechanism is cognitive competition: a demanding visuospatial task may interfere with the visual memory processes that help intrusive images persist.",
      "asset_key":"satoshi/library/conceptual_broll/SAT-BRL-002.png",
      "asset_name":"mechanism.png","title":"THE MECHANISM",
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-003.mp3","sfx_name":"mechanism-shift.mp3"
    },
    {
      "id":"joke","mode":"joke","kind":"video",
      "text":"Which is awkward if your investment thesis was: blocks, but regulated.",
      "asset_key":"satoshi/characters/satoshi-v1/silent/SAT-SIL-007.mp4",
      "asset_name":"deadpan.mp4","title":"SATOSHI",
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-004.mp3","sfx_name":"joke-button.mp3"
    },
    {
      "id":"correction","mode":"evidence","kind":"correction",
      "text":"Tetris is not a PTSD treatment. The study tested intrusive memories after trauma, not a commercial therapeutic.",
      "data":{"heard":"Tetris treats PTSD"},
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-009.mp3","sfx_name":"claim-break.mp3"
    },
    {
      "id":"thesis","mode":"landing","kind":"thesis",
      "text":"The interesting question is how much therapeutic machinery already exists inside ordinary software — and whether anyone has proved the mechanism matters.",
      "sfx_key":"satoshi/library/audio/sfx/SAT-SFX-007.mp3","sfx_name":"thesis-land.mp3"
    }
]

BED_KEY="satoshi/library/audio/beds/SAT-BED-001.mp3"

def env_guard():
    req=["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    miss=[x for x in req if not (os.environ.get(x) or "").strip()]
    if miss: raise ValueError("Missing configuration: "+", ".join(miss))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def rid(beat,settings):
    raw=json.dumps({"beat":beat["id"],"text":beat["text"],"settings":settings},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]

def archive_for(asset_id, public_name):
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
        with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
            shutil.copyfileobj(src,dst)
        public_target=PUBLIC/public_name
        shutil.copy2(target, public_target)
        return [media_store.persist(target,f"satoshi/episodes/library-first-tetris/audio/{target.name}")]
    return archive

def download(url,target):
    target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
        shutil.copyfileobj(src,dst)

def probe(path):
    out=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],text=True)
    return float(out.strip())

def main():
    env_guard()
    p=json.loads(PRESETS.read_text())
    if p["preset_id"]!="Clint": raise ValueError("Canonical voice is not Clint")
    PUBLIC.mkdir(parents=True,exist_ok=True)
    voice_files=[]
    voice_results=[]
    for i,beat in enumerate(BEATS,1):
        cfg=p["delivery_presets"][beat["mode"]]
        body={
          "model":"eleven_v4",
          "promptText":beat["text"],
          "voice":{"type":"runway-preset","presetId":"Clint"},
          "stability":cfg["stability"],"similarityBoost":cfg["similarityBoost"],
          "style":cfg["style"],"speed":cfg["speed"],"useSpeakerBoost":cfg["useSpeakerBoost"],
          "languageCode":"en"
        }
        req={"operation":"post_text_to_speech","request_id":rid(beat,cfg),"allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,"body":body}
        result=runway_operation.execute(req,archive=archive_for(f"TETRIS-VOX-{i:02d}",f"voice-{i:02d}.mp3"),job_root=JOB_ROOT,work_root=WORK_ROOT)
        media=result.get("media",[])
        if result.get("state")!="completed" or len(media)!=1: raise RuntimeError(f"Voice beat {beat['id']} failed")
        local=PUBLIC/f"voice-{i:02d}.mp3"
        voice_files.append(local)
        voice_results.append({"beat":beat["id"],"media":media[0]})

    concat=ROOT/"outputs/library-first-pilot/concat.txt"
    concat.parent.mkdir(parents=True,exist_ok=True)
    concat.write_text("\n".join([f"file '{p.resolve()}'" for p in voice_files])+"\n")
    narration=PUBLIC/"narration.mp3"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),"-c:a","libmp3lame","-b:a","192k",str(narration)],check=True)

    media_store.fetch(BED_KEY,PUBLIC/"bed.mp3")
    out_beats=[]
    frame=0
    fps=30
    for beat,voice_path in zip(BEATS,voice_files):
        dur=max(1,round(probe(voice_path)*fps))
        item={"id":beat["id"],"from":frame,"duration":dur,"kind":beat["kind"],"text":beat["text"]}
        for k in ("title","citation","data"):
            if k in beat: item[k]=beat[k]
        if beat.get("asset_key"):
            media_store.fetch(beat["asset_key"],PUBLIC/beat["asset_name"])
            item["asset"]="pilot-assets/"+beat["asset_name"]
        if beat.get("sfx_key"):
            media_store.fetch(beat["sfx_key"],PUBLIC/beat["sfx_name"])
            item["sfx"]="pilot-assets/"+beat["sfx_name"]
        out_beats.append(item)
        frame+=dur

    payload={
      "fps":fps,"width":1080,"height":1920,"duration_frames":frame,
      "narration":"pilot-assets/narration.mp3",
      "background_bed":"pilot-assets/bed.mp3",
      "beats":out_beats
    }
    MANIFEST.write_text(json.dumps(payload,indent=2)+"\n")
    result={"state":"ready_to_render","duration_frames":frame,"duration_seconds":frame/fps,"voice_assets":voice_results,"manifest":str(MANIFEST.relative_to(ROOT))}
    out=ROOT/"outputs/library-first-pilot/build-result.json"
    out.write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
