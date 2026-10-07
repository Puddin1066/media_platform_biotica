from __future__ import annotations
import hashlib, json, os, shutil, subprocess, urllib.parse, urllib.request
from pathlib import Path
import media_store, runway_media, runway_operation
from satoshi_v2.schema import digest

ROOT=Path(__file__).resolve().parents[1]
IDENTITY_PATH=ROOT/"studio/characters/satoshi-v1/canonical_identity.json"

def _archive(prefix,key_prefix):
    def archive(response,job_id,work):
        urls=response.get("output",[])
        if isinstance(urls,dict):
            urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(f"{prefix}: expected one provider output")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".bin"
        target=Path(work)/(prefix+suffix); target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
            shutil.copyfileobj(src,dst)
        return [media_store.persist(target,f"{key_prefix}/{target.name}")]
    return archive

def _execute(operation,body,credits,episode_id,kind,work):
    rid=digest({"operation":operation,"body":body})[:32]
    req={"operation":operation,"request_id":rid,"allow_mutation":True,
         "allow_media_spend":True,"estimated_credits":credits,"body":body}
    return runway_operation.execute(req,archive=_archive(kind,f"satoshi-v2/{episode_id}/{kind}"),
        job_root=Path(work)/"jobs",work_root=Path(work)/"media")

def scene_image(episode,work):
    identity=json.loads(IDENTITY_PATH.read_text())
    ref=identity["canonical_reference"]
    scene=episode["scene"]
    prompt=(
      "@satoshi. Preserve the exact same fictional person and identity. "
      f"Environment: {scene['environment']}. Wardrobe: {scene['wardrobe']}. "
      f"Framing: {scene['framing']}. "
      "Seat or physically anchor Satoshi in the environment. Waist-up or half-body, natural adult proportions, "
      "face clearly visible, grounded photoreal documentary realism, one person only, no readable text or logos."
    )[:1000]
    body={"model":"gen4_image_turbo","promptText":prompt,"ratio":"720:1280",
          "referenceImages":[{"uri":ref["url"],"tag":"satoshi"}]}
    result=_execute("post_text_to_image",body,2,episode["episode_id"],"scene",work)
    media=result.get("media") or []
    if result.get("state")!="completed" or len(media)!=1: raise RuntimeError("Scene image failed")
    target=Path(work)/"scene.png"; media_store.fetch(media[0]["key"],target)
    return target,media[0]

def clint_tts(episode,beat,work):
    body={"model":"eleven_v4","promptText":beat["text"],
          "voice":{"type":"runway-preset","presetId":"Clint"},
          "stability":0.55,"similarityBoost":0.78,"style":0.22,
          "speed":float(beat.get("speed",1.04)),"useSpeakerBoost":True,"languageCode":"en"}
    result=_execute("post_text_to_speech",body,1,episode["episode_id"],f"voice-{beat['id']}",work)
    media=result.get("media") or []
    if result.get("state")!="completed" or len(media)!=1: raise RuntimeError("TTS failed")
    target=Path(work)/f"{beat['id']}.mp3"; media_store.fetch(media[0]["key"],target)
    return target,media[0]

def duration(path):
    return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
      "-of","default=nw=1:nk=1",str(path)],text=True).strip())

def act_two(episode,beat,scene_path,audio_path,work):
    seconds=duration(audio_path)
    if not 3 <= seconds <= 6.5:
        raise ValueError(f"Host beat {beat['id']} must be 3-6.5 seconds, got {seconds:.2f}")
    driver=Path(work)/f"driver-{beat['id']}.mp4"
    ledger=Path(work)/"driver-ledger"/beat["id"]; ledger.mkdir(parents=True,exist_ok=True)
    import plate_host
    plate_host._submit_or_reuse_avatar(audio_path,ledger,os.environ["RUNWAY_AVATAR_ID"],driver,True)
    client=runway_media.client_from_environment()
    with Path(scene_path).open("rb") as fh: scene_uri=client.uploads.create_ephemeral(file=fh).uri
    with driver.open("rb") as fh: driver_uri=client.uploads.create_ephemeral(file=fh).uri
    body={"model":"act_two","character":{"type":"image","uri":scene_uri},
          "reference":{"type":"video","uri":driver_uri},"bodyControl":True,
          "expressionIntensity":int(beat.get("expression_intensity",2)),"ratio":"720:1280"}
    result=_execute("post_character_performance",body,max(1,int(seconds*5+0.999)),
                    episode["episode_id"],f"host-{beat['id']}",work)
    media=result.get("media") or []
    if result.get("state")!="completed" or len(media)!=1: raise RuntimeError("Act Two failed")
    target=Path(work)/f"host-{beat['id']}.mp4"; media_store.fetch(media[0]["key"],target)
    return target,media[0]
