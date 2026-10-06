"""Produce the direct Satoshi Tetris final: narration + configured avatar + Remotion manifest."""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import episode
import remotion_handoff
from studio import digest
from direct_tetris_remotion import _artifact_source


BEATS=("opening","explanations","evidence","limits","next_test")


def prepare(spec_path: str|Path, root: str|Path) -> Path:
    spec=json.loads(Path(spec_path).read_text(encoding="utf-8"))
    root=Path(root)
    root.mkdir(parents=True, exist_ok=True)
    cues=[]
    source_urls=[s["url"] for s in spec.get("sources",[])]
    for beat in spec["beats"]:
        cues.append({
            "cue_id":beat["cue_id"],
            "spoken_text":beat["text"],
            "claim_ids":["direct-tetris:"+digest({"beat":beat["cue_id"],"text":beat["text"]})[:12]],
            "source_urls":source_urls if beat["cue_id"] in {"evidence","limits"} else [],
            "search_query":beat["text"],
        })
    board={
        "schema_version":1,
        "topic":spec["title"],
        "script_sha256":digest(spec["beats"]),
        "reviewer":"DIRECT_SATOSHI_FINAL",
        "cues":cues,
        "status":"awaiting_footage",
        "publishable":False,
        "review_status":"unreviewed_web_preview",
    }
    path=root/"storyboard.json"
    path.write_text(json.dumps(board,indent=2)+"\n",encoding="utf-8")
    return path


def wait_audio(root: Path, voice_id: str, timeout=1200, interval=10):
    episode.submit_audio(root, voice_id, live=True)
    deadline=time.monotonic()+timeout
    while True:
        states=episode.collect_audio(root, voice_id)
        if all(states.get(b)=="audio_ready" for b in BEATS):
            return states
        bad={k:v for k,v in states.items() if v in {"failed","cancelled","reserved_unknown","rejected_no_task"}}
        if bad:
            raise RuntimeError("Narration generation failed: "+repr(bad))
        if time.monotonic()>=deadline:
            raise TimeoutError("Timed out waiting for narration: "+repr(states))
        time.sleep(interval)


def wait_host(root: Path, avatar_id: str, timeout=1800, interval=15):
    submitted=episode.submit_host(root,"avatar",live=True,avatar_id=avatar_id)
    record=submitted.get("record")
    if not record:
        raise RuntimeError("Avatar submission did not return a durable record")
    rel=str(Path(record).resolve().relative_to(root.resolve()))
    deadline=time.monotonic()+timeout
    while True:
        state=episode.collect_host(root,rel)
        if state.get("state")=="collected":
            return Path(state["file"])
        if state.get("state") in {"failed","cancelled","reserved_unknown","rejected_no_task"}:
            raise RuntimeError("Avatar generation failed: "+repr(state))
        if time.monotonic()>=deadline:
            raise TimeoutError("Timed out waiting for avatar: "+repr(state))
        time.sleep(interval)


def build_remotion(spec_path: str|Path, edl_path: str|Path, root: str|Path,
                   asset_root: str|Path, remotion_dir: str|Path="remotion") -> Path:
    spec=json.loads(Path(spec_path).read_text(encoding="utf-8"))
    edl=json.loads(Path(edl_path).read_text(encoding="utf-8"))
    root=Path(root)
    remotion=Path(remotion_dir)
    assets=remotion/"public"/"direct-assets"
    assets.mkdir(parents=True,exist_ok=True)

    # Generated Satoshi + locked narration.
    shutil.copyfile(root/"generated"/"host.mp4", assets/"satoshi-host.mp4")
    shutil.copyfile(root/"generated"/"narration.wav", assets/"satoshi-narration.wav")

    # Reuse the already-paid strongest Runway visuals from the successful batch.
    selected={
        "memory_video":("memory.mp4","0.mp4"),
        "software_video":("software.mp4","0.mp4"),
        "engagement_video":("engagement.mp4","0.mp4"),
    }
    artifact=Path(asset_root)
    for key,(dest,source_name) in selected.items():
        shutil.copyfile(_artifact_source(edl["sources"][key],artifact,source_name),assets/dest)

    timing=json.loads((root/"generated"/"timing.json").read_text(encoding="utf-8"))
    seg={x["cue_id"]:x for x in timing["segments"]}
    sources=spec["sources"]

    def visual(beat_id, role, *, video=None, vtype="illustration", text="", label="", citations=None,
               start=None,end=None):
        s=seg[beat_id]
        first=s["start_frame"] if start is None else start
        last=s["end_frame"] if end is None else end
        return {
            "beat_id":role,
            "role":role,
            "text":text,
            "citations":citations or [],
            "still":"",
            "inset_video":video,
            "motion":"hold",
            "from":first,
            "duration":max(1,last-first),
            "visual_type":vtype,
            "screen_text":text,
            "source_label":label,
            "playback_rate":1,
        }

    beats=[]
    beats.append(visual("opening","opening_host",vtype="host",text=spec["beats"][0]["text"]))

    beats.append(visual(
        "explanations","mechanism",
        video="direct-assets/memory.mp4",
        text="Visuospatial competition with intrusive visual memory",
        label="AI ILLUSTRATION — MECHANISM HYPOTHESIS",
    ))

    beats.append(visual(
        "evidence","evidence_receipt",
        vtype="typography",
        text="Randomized studies: fewer later intrusive memories in some settings",
        label=sources[0]["label"],
        citations=[sources[0]["url"],sources[1]["url"]],
    ))

    beats.append(visual(
        "limits","limits",
        video="direct-assets/engagement.mp4",
        text="Not an established PTSD treatment",
        label="CLAIM LIMIT",
        citations=[sources[0]["url"]],
    ))

    nxt=seg["next_test"]
    split=nxt["start_frame"]+round((nxt["end_frame"]-nxt["start_frame"])*0.58)
    beats.append(visual(
        "next_test","commercial_thesis",
        video="direct-assets/software.mp4",
        text="Search existing software for latent therapeutic mechanisms",
        label="SATOSHI / COMMERCIAL THESIS",
        start=nxt["start_frame"],end=split,
    ))
    beats.append(visual(
        "next_test","closing_host",
        vtype="host",
        text="Engagement is not efficacy. Test the mechanic.",
        start=split,end=nxt["end_frame"],
    ))

    direct={
        "title":spec["title"],
        "host":"direct-assets/satoshi-host.mp4",
        "voice":"direct-assets/satoshi-narration.wav",
        "loop_host":False,
        "cutaway_from_frame":None,
        "captions":remotion_handoff.captions_from_timing(timing),
        "beats":beats,
        "duration_frames":timing["duration_frames"],
        "fps":timing["fps"],
        "width":1080,
        "height":1920,
    }
    target=remotion/"public"/"direct-episode.json"
    target.write_text(json.dumps(direct,indent=2)+"\n",encoding="utf-8")
    return target


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",default="production_specs/tetris_satoshi_final.json")
    p.add_argument("--edl",default="production_specs/tetris_edit_decision.json")
    p.add_argument("--root",default="outputs/tetris-satoshi-final")
    p.add_argument("--asset-root",required=True)
    p.add_argument("--remotion-dir",default="remotion")
    p.add_argument("--voice-id",required=True)
    p.add_argument("--avatar-id",required=True)
    p.add_argument("--live",action="store_true")
    args=p.parse_args()

    root=Path(args.root)
    prepare(args.spec,root)
    if not args.live:
        print(root/"storyboard.json")
        return
    wait_audio(root,args.voice_id)
    episode.narration(root)
    wait_host(root,args.avatar_id)
    target=build_remotion(args.spec,args.edl,root,args.asset_root,args.remotion_dir)
    print(target)


if __name__=="__main__":
    main()
