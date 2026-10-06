"""Build the fail-closed directed Satoshi episode for the current request.

This is the only production builder allowed to render the canonical directed
Satoshi format. It reuses the approved abandoned-arcade scene, generates Clint
speech by beat, creates synchronized Act Two host clips only for persona-bearing
beats, builds the Remotion manifest, renders, persists, and optionally publishes.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import media_store, plate_host, runway_media, runway_operation
import openai_stills

PUBLIC=ROOT/"remotion/public/directed-assets"
MANIFEST=ROOT/"remotion/public/canonical-episode.json"
OUT=ROOT/"outputs/directed-satoshi"
SCENE_KEY="satoshi/acceptance/tetris-realism/scene.png"
MECHANISM_KEY="satoshi/library/conceptual_broll/SAT-BRL-002.png"
FPS=30
CURRENT_EDIT_ONLY=False

def guard(request):
    required=["RUNWAYML_API_SECRET","RUNWAY_AVATAR_ID","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID",
              "R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing=[k for k in required if not (os.environ.get(k) or "").strip()]
    if missing: raise ValueError("Missing configuration: "+", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED")!="true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")
    contract=json.loads((ROOT/"studio/director/canonical_directed_runtime.json").read_text())
    if contract.get("fallback_policy")!="fail_closed":
        raise RuntimeError("Directed runtime must fail closed")
    if request.get("environment")!="abandoned arcade":
        raise RuntimeError("This production requires the abandoned arcade episode world")
    if request.get("voice")!="Clint":
        raise RuntimeError("Canonical directed Satoshi requires Clint")
    if not request.get("beats") or not any(b.get("kind")=="host" for b in request["beats"]):
        raise RuntimeError("Directed episode requires synchronized host beats")
    publications={p.get("id"):p for p in (request.get("source_graph") or {}).get("publications",[])}
    for beat in request["beats"]:
        if beat.get("visual_type")=="publication":
            ref=beat.get("publication_ref")
            pub=publications.get(ref)
            if not pub:
                raise RuntimeError(f"Publication beat {beat.get('id')} is missing structured publication metadata")
            for field in ("title","journal","year","authors","institutions","finding","source_url"):
                if not pub.get(field):
                    raise RuntimeError(f"Publication {ref} missing required field: {field}")
    first=request["beats"][0]
    if first.get("kind")!="host" or first.get("motion_first") is not True:
        raise RuntimeError("First beat must be a motion-first synchronized host hook")

def stable_id(kind, beat_id, text):
    return hashlib.sha256((kind+"\n"+beat_id+"\n"+text).encode()).hexdigest()[:32]

def archive(prefix, key_prefix):
    def _archive(response, job_id, work):
        urls=response.get("output",[])
        if isinstance(urls,dict):
            urls=[u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls=[u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls)!=1: raise RuntimeError(prefix+": expected one provider output")
        url=urls[0]
        suffix=Path(urllib.parse.urlsplit(url).path).suffix or ".bin"
        target=Path(work)/(prefix+suffix); target.parent.mkdir(parents=True,exist_ok=True)
        with urllib.request.urlopen(url,timeout=180) as src,target.open("wb") as dst:
            shutil.copyfileobj(src,dst)
        return [media_store.persist(target,f"{key_prefix}/{prefix}{suffix}")]
    return _archive

def probe(path):
    raw=subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration",
      "-of","default=noprint_wrappers=1:nokey=1",str(path)],text=True)
    return float(raw.strip())

def tts(beat, presets):
    cached=OUT/f"{beat['id']}.mp3"
    cached_key=f"satoshi/episodes/directed-tetris/audio/voice-{beat['id']}.mp3"
    try:
        media_store.fetch(cached_key,cached)
        print(f"REUSE_TTS {beat['id']} {cached_key}")
        return cached
    except Exception:
        if CURRENT_EDIT_ONLY:
            raise RuntimeError(f"EDIT_ONLY requires persisted narration asset: {cached_key}")
        pass
    mode=beat["delivery"]
    cfg=dict(presets["delivery_presets"][mode])
    if "speed" in beat: cfg["speed"]=beat["speed"]
    req={
      "operation":"post_text_to_speech",
      "request_id":stable_id("tts",beat["id"],beat["text"]),
      "allow_mutation":True,"allow_media_spend":True,"estimated_credits":1,
      "body":{"model":"eleven_v4","promptText":beat["text"],
              "voice":{"type":"runway-preset","presetId":"Clint"},
              "stability":cfg["stability"],"similarityBoost":cfg["similarityBoost"],
              "style":cfg["style"],"speed":cfg["speed"],
              "useSpeakerBoost":cfg["useSpeakerBoost"],"languageCode":"en"}
    }
    result=runway_operation.execute(req,archive=archive("voice-"+beat["id"],"satoshi/episodes/directed-tetris/audio"),
      job_root=OUT/"tts-jobs",work_root=OUT/"tts-work")
    if result.get("state")!="completed" or len(result.get("media",[]))!=1:
        raise RuntimeError("Clint TTS failed for "+beat["id"])
    path=OUT/f"{beat['id']}.mp3"
    media_store.fetch(result["media"][0]["key"],path)
    return path

def host_clip(beat, audio, scene_url):
    cached=PUBLIC/f"host-{beat['id']}.mp4"
    cached_key=f"satoshi/episodes/directed-tetris/host/host-{beat['id']}.mp4"
    try:
        media_store.fetch(cached_key,cached)
        print(f"REUSE_HOST {beat['id']} {cached_key}")
        return cached
    except Exception:
        if CURRENT_EDIT_ONLY:
            raise RuntimeError(f"EDIT_ONLY requires persisted host asset: {cached_key}")
        pass
    driver=OUT/f"driver-{beat['id']}.mp4"
    ledger=OUT/"driver-ledger"/beat["id"]; ledger.mkdir(parents=True,exist_ok=True)
    plate_host._submit_or_reuse_avatar(audio,ledger,os.environ["RUNWAY_AVATAR_ID"],driver,True)
    client=runway_media.client_from_environment()
    with driver.open("rb") as data:
        driver_ref=client.uploads.create_ephemeral(file=data).uri
    req={
      "operation":"post_character_performance",
      "request_id":stable_id("acttwo",beat["id"],beat["text"]),
      "allow_mutation":True,"allow_media_spend":True,"estimated_credits":45,
      "body":{"model":"act_two","character":{"type":"image","uri":scene_url},
              "reference":{"type":"video","uri":driver_ref},"bodyControl":True,
              "expressionIntensity":2,"ratio":"720:1280"}
    }
    result=runway_operation.execute(req,archive=archive("host-"+beat["id"],"satoshi/episodes/directed-tetris/host"),
      job_root=OUT/"act-jobs",work_root=OUT/"act-work")
    if result.get("state")!="completed" or len(result.get("media",[]))!=1:
        raise RuntimeError("Act Two failed for "+beat["id"])
    target=PUBLIC/f"host-{beat['id']}.mp4"
    media_store.fetch(result["media"][0]["key"],target)
    return target

def edit_still(beat_id, prompt):
    """Generate/reuse one cheap editorial still. Never uses Runway."""
    key=f"satoshi/episodes/directed-tetris/edit-stills/{beat_id}.png"
    target=PUBLIC/f"{beat_id}.png"
    try:
        media_store.fetch(key,target)
        print(f"REUSE_EDIT_STILL {beat_id} {key}")
        return target
    except Exception:
        pass
    if not CURRENT_EDIT_ONLY:
        return None
    image=openai_stills.generate_still_bytes(prompt)
    target.write_bytes(image)
    media_store.persist(target,key)
    return target

def main():
    global CURRENT_EDIT_ONLY
    p=argparse.ArgumentParser()
    p.add_argument("--request",required=True)
    p.add_argument("--publish",action="store_true")
    p.add_argument("--edit-only",action="store_true",
                   help="Reuse all persisted voice/host media; forbid any Runway generation")
    args=p.parse_args()
    request=json.loads(Path(args.request).read_text())
    guard(request)
    if args.edit_only:
        CURRENT_EDIT_ONLY = True
        request.setdefault("production", {})["edit_only"] = True
    PUBLIC.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)

    # Reuse the approved arcade scene; if it is gone, fail rather than invent a fallback.
    scene_local=OUT/"scene.png"
    media_store.fetch(SCENE_KEY,scene_local)
    scene_url=media_store.public_base_url()+"/"+SCENE_KEY

    presets=json.loads((ROOT/"studio/characters/satoshi-v1/delivery_presets.json").read_text())
    if presets.get("preset_id")!="Clint": raise RuntimeError("Delivery presets are not Clint")

    mechanism=PUBLIC/"mechanism.png"
    media_store.fetch(MECHANISM_KEY,mechanism)
    pear_still=edit_still("pear-context",
        "Documentary editorial still about the prescription digital therapeutics era: an anonymous smartphone beside a clinical prescription pad and reimbursement paperwork on a dim desk, sophisticated health-tech atmosphere, no readable text, no logos, no people.")
    latent_still=edit_still("latent-software",
        "Cinematic editorial still about latent therapeutic mechanisms inside ordinary software: an old arcade cabinet glowing in a dark room beside subtle clinical research objects, grounded documentary realism, no readable text, no logos, no people.")

    publications={p.get("id"):p for p in (request.get("source_graph") or {}).get("publications",[])}
    audios=[]; host_segments=[]; remotion_beats=[]; frame=0
    for beat in request["beats"]:
        audio=tts(beat,presets); audios.append(audio)
        dur=max(1,round(probe(audio)*FPS))
        if beat["kind"]=="host":
            if dur/FPS>6.5:
                raise RuntimeError(f"Host beat {beat['id']} is {dur/FPS:.2f}s; exceeds realism limit")
            clip=host_clip(beat,audio,scene_url)
            host_segments.append({"segment_id":beat["id"],"role":beat["role"],
              "src":"directed-assets/"+clip.name,"from":frame,"duration":dur,
              "realism":{"scale_start":1.0,"scale_end":1.018,"x_start":0,"x_end":7,"y_start":0,"y_end":-3}})
        rb={"beat_id":beat["id"],"role":beat["role"],"text":beat["text"],
            "citations":beat.get("citations",[]),"still":"","motion":"hold",
            "from":frame,"duration":dur,"visual_type":beat.get("visual_type","host"),
            "screen_text":beat.get("screen_text",""),"source_label":beat.get("source_label",""),
            "publication":publications.get(beat.get("publication_ref"))}
        if beat.get("asset")=="mechanism":
            rb["still"]="directed-assets/mechanism.png"; rb["visual_type"]="illustration"; rb["motion"]="slow_zoom"
        if beat["id"]=="pear_short" and pear_still is not None:
            rb["still"]="directed-assets/"+pear_still.name; rb["visual_type"]="illustration"; rb["motion"]="slow_zoom"
        if beat["id"] in {"inversion_short","bigger_question_short"} and latent_still is not None:
            rb["still"]="directed-assets/"+latent_still.name; rb["visual_type"]="illustration"; rb["motion"]="slow_zoom"
        remotion_beats.append(rb); frame+=dur

    concat=OUT/"concat.txt"
    concat.write_text("\n".join("file '"+str(x.resolve())+"'" for x in audios)+"\n")
    narration=PUBLIC/"narration.mp3"
    subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(concat),
                    "-c:a","libmp3lame","-b:a","192k",str(narration)],check=True)
    seconds=probe(narration)
    if not 45.0 <= seconds <= 60.5:
        raise RuntimeError(f"Directed episode duration {seconds:.2f}s outside 45–60s target; refusing render")

    manifest={"title":request["title"],"format":"directed_satoshi","company":"Biotica",
      "host":"","host_segments":host_segments,"voice":"directed-assets/narration.mp3",
      "loop_host":False,"cutaway_from_frame":None,"captions":[],
      "beats":remotion_beats,"duration_frames":frame,"fps":FPS,"width":1080,"height":1920}
    MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n")

    subprocess.run(["npm","run","typecheck"],cwd=ROOT/"remotion",check=True)
    output_name = str(request.get("output_name") or ("directed-satoshi-tetris-edit-v2.mp4" if args.edit_only else "directed-satoshi-tetris.mp4"))
    if "/" in output_name or "\\" in output_name:
        raise ValueError("output_name must be a filename")
    subprocess.run(["npx","remotion","render","src/index.ts","CanonicalSatoshiEpisode",
                    "out/"+output_name],cwd=ROOT/"remotion",check=True,timeout=1800)
    video=ROOT/"remotion/out"/output_name
    if not video.is_file() or video.stat().st_size<=0: raise RuntimeError("Remotion render missing")
    object_key = str(request.get("output_r2_key") or (
        "satoshi/episodes/directed-tetris/directed-satoshi-tetris-edit-v2.mp4"
        if args.edit_only else "satoshi/episodes/directed-tetris/directed-satoshi-tetris-v1.mp4"))
    record=media_store.persist(video,object_key)
    media_manifest=OUT/"media-manifest.json"
    media_manifest.write_text(json.dumps({"assets":[{**record,"local_file":str(video)}]},indent=2)+"\n")
    result={"status":"rendered","duration_seconds":seconds,"video":record,"host_segments":len(host_segments)}
    if args.publish:
        if not os.environ.get("META_ACCESS_TOKEN") or not os.environ.get("IG_USER_ID"):
            raise RuntimeError("Instagram credentials missing; refusing publish")
        subprocess.run(["python","publish_satoshi_instagram.py","--video",str(video),
          "--manifest",str(media_manifest),"--request",args.request,
          "--ledger",str(OUT/"instagram-posts.sqlite"),"--live",
          "--reviewer","directed-satoshi-production","--output",str(OUT/"instagram-publish.json")],
          cwd=ROOT,check=True)
        result["status"]="published"
    (OUT/"result.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))

if __name__=="__main__": main()
