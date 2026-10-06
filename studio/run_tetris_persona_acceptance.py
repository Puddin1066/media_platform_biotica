"""Paid acceptance test: Satoshi speaks one Tetris persona hook in an abandoned arcade."""
from __future__ import annotations
import json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import media_store
import plate_host
import runway_host
import runway_operation

OUT=ROOT/"outputs/persona-acceptance-tetris"
OUT.mkdir(parents=True,exist_ok=True)

SOURCE_KEY="satoshi/characters/satoshi-v1/silent/SAT-SIL-007.mp4"
LINE=("I spent six months consulting for an arcade chain that went bankrupt before the invoice cleared. "
      "Tetris was the only machine anyone still played.")
ALEPH_PROMPT=(
    "Place the same canonical Satoshi character inside an abandoned 1980s-style arcade at night. "
    "One old block-puzzle arcade cabinet glows over his shoulder; other cabinets are dark, dusty, and partially covered. "
    "Change his clothing to a rumpled dark overshirt over a charcoal T-shirt, no suit, no tie. "
    "Add a worn paper invoice folder tucked under one arm as a subtle prop. "
    "Lighting comes mostly from the arcade cabinet glow with dim practical ceiling lights. "
    "Medium shot, face clearly visible, cinematic but realistic, restrained camera movement. "
    "Preserve the exact person's identity, facial anatomy, age, hairline, skin, body proportions and recognizable appearance. "
    "No captions, no text overlays, no extra people, no face replacement."
)

def guard():
    required=["RUNWAYML_API_SECRET","RUNWAY_AVATAR_ID","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing=[k for k in required if not (os.environ.get(k) or "").strip()]
    if missing:
        raise ValueError("Missing configuration: "+", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def archive_tts(response,job_id,work):
    urls=response.get("output",[])
    if isinstance(urls,dict):
        urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
    urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
    if len(urls)!=1:
        raise RuntimeError("Expected exactly one TTS output")
    url=urls[0]
    suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".mp3"
    target=Path(work)/("tetris-persona-hook"+suffix)
    target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
        shutil.copyfileobj(src,dst)
    return [media_store.persist(target,"satoshi/acceptance/tetris-persona-hook/audio"+suffix)]

def main():
    guard()
    source=OUT/"source.mp4"
    media_store.fetch(SOURCE_KEY,source)

    tts_req={
      "operation":"post_text_to_speech",
      "request_id":"9c7fd4b59eb84d8f9d82e0cfad01c2e1",
      "allow_mutation":True,
      "allow_media_spend":True,
      "estimated_credits":1,
      "body":{
        "model":"eleven_v4",
        "promptText":LINE,
        "voice":{"type":"runway-preset","presetId":"Clint"},
        "stability":0.34,
        "similarityBoost":0.72,
        "style":0.42,
        "speed":1.07,
        "useSpeakerBoost":True,
        "languageCode":"en"
      }
    }
    tts=runway_operation.execute(
        tts_req,archive=archive_tts,
        job_root=OUT/"tts-jobs",work_root=OUT/"tts-work")
    if tts.get("state")!="completed" or not tts.get("media"):
        raise RuntimeError("Clint TTS failed")
    audio=OUT/"hook.mp3"
    media_store.fetch(tts["media"][0]["key"],audio)

    artifacts=OUT/"runway-artifacts"
    work=OUT/"runway-work"
    plate,plate_record=runway_host.prepare_plate(
        source,{"prompt":ALEPH_PROMPT,"seconds":4,"offset_seconds":0},
        artifacts,work/"aleph")

    driver=OUT/"driver.mp4"
    ledger=OUT/"driver-ledger"
    ledger.mkdir(parents=True,exist_ok=True)
    plate_host._submit_or_reuse_avatar(
        audio,ledger,os.environ["RUNWAY_AVATAR_ID"],driver,True)

    final,performance_record=runway_host.perform_segment(
        plate,driver,{"expression_intensity":3},
        artifacts,work/"act-two")

    final_copy=OUT/"satoshi-tetris-arcade-hook-v1.mp4"
    shutil.copyfile(final,final_copy)
    persisted=media_store.persist(
        final_copy,"satoshi/acceptance/tetris-persona-hook/satoshi-tetris-arcade-hook-v1.mp4")

    result={
      "status":"completed",
      "spoken_line":LINE,
      "source_key":SOURCE_KEY,
      "environment":"abandoned arcade",
      "wardrobe":"rumpled dark overshirt over charcoal T-shirt",
      "tts_media":tts["media"][0],
      "aleph":plate_record,
      "act_two":performance_record,
      "final_media":persisted,
      "visual_review":"required"
    }
    (OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
