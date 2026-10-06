"""Second paid realism acceptance: image-based waist-up seated Satoshi in abandoned arcade."""
from __future__ import annotations
import json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
import media_store, plate_host, runway_operation, runway_media

OUT=ROOT/"outputs/persona-acceptance-tetris-realism"
OUT.mkdir(parents=True,exist_ok=True)

REF_URL="https://pub-215ec4ad478a482dbf4497eb2e56aba2.r2.dev/satoshi/characters/satoshi-v1/references/SAT-REF-005.png"
LINE=("I consulted for an arcade chain that was technically bankrupt. "
      "Tetris was the only machine still earning quarters. "
      "We thought nostalgia. Apparently, we should have been measuring intrusive memories.")

def guard():
    req=["RUNWAYML_API_SECRET","RUNWAY_AVATAR_ID","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    miss=[k for k in req if not (os.environ.get(k) or "").strip()]
    if miss: raise ValueError("Missing configuration: "+", ".join(miss))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true": raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def archive_one(prefix):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict):
            urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(prefix+": expected exactly one output")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or (".png" if "scene" in prefix else ".mp3")
        target=Path(work)/(prefix+suffix)
        target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst: shutil.copyfileobj(src,dst)
        return [media_store.persist(target,f"satoshi/acceptance/tetris-realism/{prefix}{suffix}")]
    return archive

def main():
    guard()
    # 1) Generate a clean seated, waist-up scene still from canonical seated Satoshi.
    scene_req={
      "operation":"post_text_to_image",
      "request_id":"41d6f8a3e6a845c8b707c93d62aa11ef",
      "allow_mutation":True,"allow_media_spend":True,"estimated_credits":2,
      "body":{
        "model":"gen4_image_turbo",
        "ratio":"720:1280",
        "referenceImages":[{"uri":REF_URL,"tag":"satoshi"}],
        "promptText":(
          "@satoshi, preserve the exact same person and realistic adult body proportions. "
          "Photorealistic waist-up medium shot, seated sideways on a worn stool beside an old block-puzzle arcade cabinet in a dim abandoned arcade. "
          "His torso and shoulders are fully visible and naturally proportioned; head is normal adult scale relative to body. "
          "Rumpled dark overshirt over charcoal T-shirt, no suit, no tie. "
          "One forearm rests casually on the cabinet edge, the other hand relaxed and visible. "
          "He is turned slightly toward camera, calm skeptical expression, direct but not rigid eye contact. "
          "Cabinet glow lights one side of his face; dim practical ceiling lights behind him. "
          "Shallow depth of field, grounded documentary realism, no heroic low angle, no caricature, no exaggerated head, one person only, no text."
        )
      }
    }
    scene=runway_operation.execute(scene_req,archive=archive_one("scene"),
      job_root=OUT/"scene-jobs",work_root=OUT/"scene-work")
    if scene.get("state")!="completed" or not scene.get("media"): raise RuntimeError("Scene image generation failed")

    # 2) Generate canonical Clint hook audio.
    tts_req={
      "operation":"post_text_to_speech",
      "request_id":"e4280e5b2d0d4fd389c1e5fb11b7a911",
      "allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,
      "body":{"model":"eleven_v4","promptText":LINE,
              "voice":{"type":"runway-preset","presetId":"Clint"},
              "stability":0.34,"similarityBoost":0.72,"style":0.36,"speed":1.06,
              "useSpeakerBoost":True,"languageCode":"en"}
    }
    tts=runway_operation.execute(tts_req,archive=archive_one("audio"),
      job_root=OUT/"tts-jobs",work_root=OUT/"tts-work")
    if tts.get("state")!="completed" or not tts.get("media"): raise RuntimeError("TTS failed")
    audio=OUT/"hook.mp3"; media_store.fetch(tts["media"][0]["key"],audio)

    # 3) Create a driver performance carrying the exact audio.
    driver=OUT/"driver.mp4"; ledger=OUT/"driver-ledger"; ledger.mkdir(parents=True,exist_ok=True)
    plate_host._submit_or_reuse_avatar(audio,ledger,os.environ["RUNWAY_AVATAR_ID"],driver,True)

    # 4) Act Two directly from the scene IMAGE; body control on, low expression intensity.
    driver_ref=runway_media.upload_and_get_uri(driver)
    body={
      "model":"act_two",
      "character":{"type":"image","uri":scene["media"][0]["url"]},
      "reference":{"type":"video","uri":driver_ref},
      "bodyControl":True,
      "expressionIntensity":2,
      "ratio":"720:1280"
    }
    act_req={
      "operation":"post_character_performance",
      "request_id":"4a2ab6e4d11e4c8f9f1a293715d3c3a8",
      "allow_mutation":True,"allow_media_spend":True,
      "estimated_credits":45,
      "body":body
    }
    act=runway_operation.execute(act_req,job_root=OUT/"act-jobs",work_root=OUT/"act-work")
    if act.get("state")!="completed" or not act.get("media"): raise RuntimeError("Act Two failed")

    final=OUT/"satoshi-tetris-arcade-realism-v2.mp4"
    media_store.fetch(act["media"][0]["key"],final)
    persisted=media_store.persist(final,"satoshi/acceptance/tetris-realism/satoshi-tetris-arcade-realism-v2.mp4")
    result={
      "status":"completed","spoken_line":LINE,
      "scene_media":scene["media"][0],"tts_media":tts["media"][0],
      "act_two":act.get("response"),"final_media":persisted,
      "staging":{"framing":"waist-up seated","body_control":True,"expression_intensity":2,"character_input":"image"},
      "visual_review":"required"
    }
    (OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
