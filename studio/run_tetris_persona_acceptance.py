"""Paid acceptance test v2: waist-up seated Satoshi in an abandoned arcade."""
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

OUT=ROOT/"outputs/persona-acceptance-tetris-v2"
OUT.mkdir(parents=True,exist_ok=True)

SOURCE_IMAGE_URL="https://pub-215ec4ad478a482dbf4497eb2e56aba2.r2.dev/satoshi/characters/satoshi-v1/references/SAT-REF-005.png"
LINE="I once consulted for an arcade chain. They went bankrupt before they paid me."
MOTION_PROMPT=(
    "Preserve the exact same man's identity and proportions. Waist-up seated shot. "
    "He is seated comfortably, torso naturally proportioned, shoulders relaxed. "
    "He glances down briefly toward controls just out of frame, then looks back toward camera. "
    "One natural blink, subtle breathing, tiny head movement only. Hands remain low and mostly out of frame. "
    "No speech, no exaggerated gesture, no camera movement, no body morphing, no face morphing."
)
ALEPH_PROMPT=(
    "Keep this exact same person, body proportions, seated waist-up framing and subtle motion. "
    "Move him into a realistic abandoned arcade at night. One old block-puzzle arcade cabinet glows beside him; "
    "other cabinets recede into darkness, dusty and partly covered. He is seated on a simple arcade stool, angled slightly toward the cabinet. "
    "Change clothing to a rumpled dark overshirt over a charcoal T-shirt, no suit and no tie. "
    "A worn paper invoice folder rests on the cabinet beside him. "
    "Lighting comes from the cabinet screen plus dim practical ceiling lights. "
    "Keep his face clearly visible and realistically proportioned to his torso. "
    "No captions, no text overlays, no extra people, no face replacement, no enlarged head."
)

def guard():
    required=["RUNWAYML_API_SECRET","RUNWAY_AVATAR_ID","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing=[k for k in required if not (os.environ.get(k) or "").strip()]
    if missing:
        raise ValueError("Missing configuration: "+", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")

def archive_one(response,job_id,work,prefix):
    urls=response.get("output",[])
    if isinstance(urls,dict):
        urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
    urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
    if len(urls)!=1:
        raise RuntimeError("Expected exactly one media output")
    url=urls[0]
    suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".mp4"
    target=Path(work)/(prefix+suffix)
    target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
        shutil.copyfileobj(src,dst)
    return [media_store.persist(target,f"satoshi/acceptance/tetris-persona-v2/{prefix}{suffix}")]

def main():
    guard()

    motion_req={
      "operation":"post_image_to_video",
      "request_id":"5d351df1ca8f46f28ca4adfd98a61021",
      "allow_mutation":True,
      "allow_media_spend":True,
      "estimated_credits":20,
      "body":{
        "model":"gen4_turbo",
        "promptImage":SOURCE_IMAGE_URL,
        "promptText":MOTION_PROMPT,
        "ratio":"720:1280",
        "duration":4
      }
    }
    motion=runway_operation.execute(
        motion_req,
        archive=lambda response,job_id,work: archive_one(response,job_id,work,"seated-motion"),
        job_root=OUT/"motion-jobs",work_root=OUT/"motion-work")
    if motion.get("state")!="completed" or not motion.get("media"):
        raise RuntimeError("Seated motion generation failed")
    source=OUT/"seated-motion.mp4"
    media_store.fetch(motion["media"][0]["key"],source)

    tts_req={
      "operation":"post_text_to_speech",
      "request_id":"5d351df1ca8f46f28ca4adfd98a61022",
      "allow_mutation":True,
      "allow_media_spend":True,
      "estimated_credits":1,
      "body":{
        "model":"eleven_v4",
        "promptText":LINE,
        "voice":{"type":"runway-preset","presetId":"Clint"},
        "stability":0.34,
        "similarityBoost":0.72,
        "style":0.32,
        "speed":1.04,
        "useSpeakerBoost":True,
        "languageCode":"en"
      }
    }
    tts=runway_operation.execute(
        tts_req,
        archive=lambda response,job_id,work: archive_one(response,job_id,work,"audio"),
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
        plate,driver,{"expression_intensity":2},
        artifacts,work/"act-two")

    final_copy=OUT/"satoshi-tetris-arcade-hook-v2.mp4"
    shutil.copyfile(final,final_copy)
    persisted=media_store.persist(
        final_copy,"satoshi/acceptance/tetris-persona-v2/satoshi-tetris-arcade-hook-v2.mp4")

    result={
      "status":"completed",
      "version":"v2-waist-up-seated",
      "spoken_line":LINE,
      "source_image":SOURCE_IMAGE_URL,
      "environment":"abandoned arcade",
      "blocking":"seated waist-up, small glance to controls then camera",
      "wardrobe":"rumpled dark overshirt over charcoal T-shirt",
      "facial_expression_intensity":2,
      "motion_media":motion["media"][0],
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
