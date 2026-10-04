"""Executable media stages for the current Satoshi Studio control plane.

Editorial artifacts remain in Studio. This module compiles those artifacts into
contracts understood by Production B's existing Remotion renderer, without
regenerating narration. R2 holds binaries, allowing each stage to run in its own
GitHub Actions job. Hashes prevent old assets being paired with a new script.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import subprocess
import wave
from pathlib import Path

import canonical_satoshi_runtime as production
import canonical_satoshi_lipsync_runtime as lipsync
import distribution_enrichment
import media_store
import narration_alignment as alignment
import openai_stills
import plate_host
import runway_media
import render_audio_guard
import satoshi_editorial_pipeline as editorial
import studio_opportunity as opportunity


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return path


def paths(root, episode):
    return Path(root) / "studio/episodes" / episode / "artifacts", Path(root) / "outputs/studio" / episode


def selected_audio(artifacts, work):
    verdict = read(artifacts / "audio_evaluation.json")
    if verdict.get("regenerate"):
        raise ValueError("Audio judge requested regeneration; media production is blocked")
    ref = verdict["selected_audio"]
    target = Path(work) / "selected.wav"
    fetched = media_store.fetch(ref["key"], target)
    if fetched["sha256"] != ref["sha256"]:
        raise ValueError("Selected narration hash mismatch")
    return target, ref


def validate_alignment(artifacts, script, audio_sha):
    timing = read(artifacts / "narration_alignment.json")
    if timing["audio_sha256"] != audio_sha or timing["script_sha256"] != editorial.sha(script):
        raise ValueError("Alignment is stale for the selected narration/script")
    return timing


def run_alignment(root, episode, request, key):
    artifacts, work = paths(root, episode)
    script = read(artifacts / "canonical_script.json")
    audio, ref = selected_audio(artifacts, work / "alignment")
    observed_path = artifacts / "alignment_observations.json"
    observed = read(observed_path) if observed_path.exists() else {}
    if observed.get("audio_sha256") == ref["sha256"] and observed.get("script_sha256") == editorial.sha(script):
        words = observed["words"]
    else:
        words = alignment.transcribe(audio, script, key)
    # Retain observations even if exact alignment fails, so spelling differences
    # can be repaired against measured intervals without retranscribing audio.
    write(artifacts / "alignment_observations.json", {"words": words, "audio_sha256": ref["sha256"],
          "script_sha256": editorial.sha(script)})
    timing = alignment.align_words(script, words, render_audio_guard.duration_seconds(audio) * 1000, ref["sha256"])
    timing["script_sha256"] = editorial.sha(script)
    return [write(artifacts / "narration_alignment.json", timing), artifacts / "alignment_observations.json"]


def compile_shots(script, plan):
    """Validate planned sentence coverage; narration remains independent of visuals."""
    ids = [s["sentence_id"] for s in script["script"]]
    shots = plan.get("shots") or []
    covered, seen = set(), set()
    for shot in shots:
        sid = shot.get("shot_id")
        if not isinstance(sid, str) or not sid.replace("-", "").replace("_", "").isalnum() or sid in seen:
            raise ValueError("Shot IDs must be unique safe filenames")
        refs = shot.get("sentence_ids") or []
        if not refs or any(ref not in ids for ref in refs):
            raise ValueError("Visual plan references unknown/empty sentence IDs")
        indexes = [ids.index(ref) for ref in refs]
        if indexes != list(range(indexes[0], indexes[0] + len(indexes))):
            raise ValueError("A shot must cover consecutive sentences in spoken order")
        if covered.intersection(refs):
            raise ValueError("Visual shots overlap; select one evidence-panel shot per sentence")
        covered.update(refs)
        seen.add(sid)
    if covered != set(ids):
        raise ValueError("Visual plan must cover every locked sentence")
    return sorted(shots, key=lambda s: ids.index(s["sentence_ids"][0]))


def run_assets(root, episode, request, key):
    artifacts, work = paths(root, episode)
    script, plan = read(artifacts / "canonical_script.json"), read(artifacts / "visual_plan.json")
    identity = {"script_sha256": editorial.sha(script), "visual_plan_sha256": editorial.sha(plan)}
    asset_dir = work / "assets" / editorial.sha(identity)
    asset_dir.mkdir(parents=True, exist_ok=True)
    shots = compile_shots(script, plan)
    if opportunity.is_brief(request):
        allowed = {"host", "typography", "chart", "evidence"}
        if any(shot.get("type") not in allowed for shot in shots):
            raise ValueError("Opportunity Brief only accepts host, typography, chart and licensed evidence")
    # Validate the complete plan before any parallel generation spends credits.
    for shot in shots:
        if shot.get("type") == "chart":
            chart = shot.get("chart") or {}
            if not chart.get("source_url") or not chart.get("points"):
                raise ValueError("Chart needs explicit data and source_url")
        if shot.get("type") == "evidence" and not (shot.get("media") or {}).get("key"):
            raise ValueError("Evidence needs explicit R2 media")
    # Shot files can be resumed within a job; durable object names include their
    # script/plan identity, so an upstream edit never overwrites prior media.
    def build_asset(shot):
        kind = str(shot.get("type", "generated illustration")).replace("_", " ")
        item = {**shot, "visual_type": "illustration", "screen_text": str(shot.get("screen_text") or "")[:120]}
        if kind in {"typography", "host"}:
            item["visual_type"] = "typography" if kind == "typography" else "host"
        elif kind == "chart":
            chart = shot.get("chart") or {}
            points = chart.get("points") or []
            if not chart.get("source_url") or not points or any(not isinstance(p.get("value"), (int, float)) or not math.isfinite(p["value"]) or p["value"] < 0 for p in points):
                raise ValueError("Chart requires nonnegative numeric points and source_url; generated imagery cannot substitute for data")
            item.update(visual_type="chart", chart=chart)
        elif kind == "evidence":
            source = shot.get("media") or {}
            if not source.get("key") or not source.get("credit"):
                raise ValueError("Evidence shot requires an explicit R2 media key and credit")
            suffix = ".mp4" if source.get("kind") == "video" else ".png"
            path = asset_dir / (shot["shot_id"] + suffix)
            fetched = media_store.fetch(source["key"], path)
            item.update(visual_type="source", media={**source, "sha256": fetched["sha256"]})
        else:
            path = asset_dir / f'{shot["shot_id"]}.png'
            if not path.exists():
                path.write_bytes(openai_stills.generate_still_bytes(
                    "Editorial illustration. " + str(shot.get("intent") or "") +
                    " No typography, no chart values, no fabricated scientific evidence or identifiable real people."))
            item["media"] = media_store.persist(path, f"satoshi-studio/{episode}/assets/{editorial.sha(identity)}/{path.name}")
        return item
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(3, len(shots))) as pool:
        assets = list(pool.map(build_asset, shots))
    return [write(artifacts / "assets_manifest.json", {**identity, "shots": assets})]


def run_host(root, episode, request, key):
    artifacts, work = paths(root, episode)
    host = dict(request.get("host") or {})
    mode = host.get("mode", "brief_canvas" if opportunity.is_brief(request) else "master_asset")
    if mode == "brief_canvas":
        if not opportunity.is_brief(request):
            raise ValueError("brief_canvas is reserved for Opportunity Brief")
        target = work / "host" / "brief-canvas.mp4"
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-f", "lavfi", "-i",
                        "color=c=0x15202b:s=1920x1080:r=30", "-t", "95",
                        "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(target)],
                       check=True, timeout=180)
        record = media_store.persist(target, f"satoshi-studio/{episode}/host/{alignment.file_sha(target)}.mp4")
        return [write(artifacts / "host_manifest.json", {
            "generated": False, "media": record, "source": "locally rendered canvas",
            "lip_sync": "not_applicable_no_avatar", "loop": True, "mode": mode})]
    if mode in {"master_asset", "background_plate"}:
        chosen = media_store.resolve_plate(episode, host.get("r2_key") or request.get("plate_r2_key"))
        return [write(artifacts / "host_manifest.json", {
            "generated": False, "source": chosen["source"], "plate": {"key": chosen["key"], "bytes": chosen.get("bytes")},
            "lip_sync": "not_applied", "loop": True,
            "note": "Background plate only. Mouth movements have not been synchronized to narration."})]
    if mode not in {"avatar", "act_two"}:
        raise ValueError("Studio host supports master_asset/background_plate, avatar, or act_two")
    audio, ref = selected_audio(artifacts, work / "host")
    script = read(artifacts / "canonical_script.json")
    timing = validate_alignment(artifacts, script, ref["sha256"])
    import os
    preset_id = (host.get("driver_preset") or os.environ.get("SATOSHI_DRIVER_PRESET") or "").strip()
    avatar_id = host.get("avatar_id") or os.environ.get("RUNWAY_AVATAR_ID")
    if not preset_id and not avatar_id:
        raise ValueError("A face-forward driver preset or RUNWAY_AVATAR_ID is required")
    identity = editorial.sha({"audio": ref["sha256"], "host": host, "avatar_id": avatar_id, "preset_id": preset_id})
    host_dir = work / "host" / identity
    host_dir.mkdir(parents=True, exist_ok=True)
    character = host_dir / "character.mp4"
    if mode == "act_two":
        chosen = media_store.resolve_plate(episode, host.get("r2_key"))
        media_store.fetch(chosen["key"], character)
        # Preserve the explicit plate selection in the job identity below.
        identity = editorial.sha({"audio": ref["sha256"], "host": host, "avatar_id": avatar_id,
                                  "preset_id": preset_id, "character_sha256": alignment.file_sha(character)})
    # Preset talking-head videos stay face-forward at about four seconds.
    # Longer references step back to a wide shot and Act-Two reports no face.
    segments = host_segments(timing, 4000 if preset_id else 30000)
    estimate = sum(2 + 2 * math.ceil((end - start) / 6000) for start, end in segments)
    if mode == "act_two":
        estimate += math.ceil(timing["duration_ms"] / 1000 * 5)
    if estimate > int(os.environ.get("PLATE_HOST_MAX_CREDITS", "650")):
        raise ValueError("Host exceeds PLATE_HOST_MAX_CREDITS")
    # Query the API project balance before reserving any new paid host task.
    # A resumed ledger may already contain paid outputs, so it is handled below.
    if not (artifacts / "host_jobs.json").exists():
        account = runway_media.client_from_environment().organization.retrieve()
        balance = account.model_dump(by_alias=True).get("creditBalance")
        write(artifacts / "host_readiness.json", {"estimated_credits": estimate,
              "available_credits": balance, "mode": mode})
        if isinstance(balance, (int, float)) and balance < estimate:
            raise ValueError(f"Runway API credits insufficient: {balance} available, {estimate} estimated")
    ledger = host_dir / "ledger"
    ledger.mkdir(parents=True, exist_ok=True)
    jobs_path = artifacts / "host_jobs.json"
    jobs = read(jobs_path) if jobs_path.exists() else {}
    if jobs.get("identity") != identity:
        jobs = {"identity": identity, "jobs": {}}
    for name, record_ref in jobs["jobs"].items():
        path = ledger / name
        media_store.fetch(record_ref["key"], path)
        record = read(path)
        if record.get("remote_media"):
            destination = host_dir / record["output_name"]
            media_store.fetch(record["remote_media"]["key"], destination)
            record["file"] = str(destination)
            write(path, record)
    def checkpoint(path, record):
        # Save a reservation BEFORE provider submission, then every state change.
        # A timeout remains reserved_unknown across Action retries, preventing
        # accidental duplicate paid submissions. Successful outputs survive jobs.
        snapshot = dict(record)
        if record.get("state") == "collected":
            generated = Path(record["file"])
            snapshot["remote_media"] = media_store.persist(generated,
                f"satoshi-studio/{episode}/host-jobs/{identity}/{generated.name}")
            snapshot["output_name"] = generated.name
        write(path, snapshot)
        jobs["jobs"][Path(path).name] = media_store.persist(path,
            f"satoshi-studio/{episode}/host-jobs/records/{Path(path).name}")
        write(jobs_path, jobs)
    previous_checkpoint = runway_media.LEDGER_CHECKPOINT
    runway_media.LEDGER_CHECKPOINT = checkpoint
    outputs = []
    try:
        for index, (start, end) in enumerate(segments):
            target = host_dir / f"host-{index}.mp4" if mode == "act_two" else host_dir / f"driver-{index}.mp4"
            if target.is_file() and abs(render_audio_guard.duration_seconds(target) * 1000 - (end - start)) <= 80:
                outputs.append(target)
                continue
            clip = host_dir / f"speech-{index}.wav"
            subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", str(start / 1000),
                            "-i", str(audio), "-t", str((end - start) / 1000), "-ar", "48000", "-ac", "2", str(clip)], check=True, timeout=120)
            driver_kwargs = {"preset_id": preset_id} if preset_id else {}
            for attempt in range(3):
                driver = host_dir / (f"driver-{index}.mp4" if attempt == 0 else f"driver-{index}-retry-{attempt}.mp4")
                kwargs = dict(driver_kwargs)
                if attempt:
                    kwargs["attempt"] = attempt
                plate_host._submit_or_reuse_avatar(clip, ledger, avatar_id, driver, True, **kwargs)
                # Timing/audio identity does not prove visible mouth quality; the
                # reviewed render is the final gate for that judgment.
                validate_driver_audio(driver, audio, start, end)
                if mode != "act_two":
                    break
                try:
                    # Use the opening of the plate for every segment. A later window of this
                    # cycling shot makes Act-Two return INTERNAL.BAD_OUTPUT, while the
                    # opening keeps the rider's face readable. Mouth timing still comes
                    # from the performance reference.
                    matched = plate_host.match_character_duration(
                        character, host_dir / f"character-{index}.mp4", (end - start) / 1000, 0)
                    plate_host._submit_or_reuse_act_two(matched, driver, ledger, target, True)
                    break
                except RuntimeError as exc:
                    retriable = any(token in str(exc) for token in ("INTERNAL.", "NO_FACE_FOUND", "unbilled retries"))
                    if attempt == 2 or not retriable:
                        raise
            if abs(render_audio_guard.duration_seconds(target) * 1000 - (end - start)) > 80:
                raise ValueError("Host output duration drift; review before assembly")
            outputs.append(target)
    finally:
        runway_media.LEDGER_CHECKPOINT = previous_checkpoint
    final = host_dir / "host.mp4"
    plate_host._concat_silent(outputs, final)
    # Each clip is quantized to the reference frame rate. Nineteen segments can
    # run a few hundred milliseconds long without dropping a sentence. A missing
    # segment is at least three seconds and still fails this check.
    frame_slop_ms = max(150, 50 * len(outputs))
    if abs(render_audio_guard.duration_seconds(final) * 1000 - timing["duration_ms"]) > frame_slop_ms:
        raise ValueError("Concatenated host duration drift")
    record = media_store.persist(final, f"satoshi-studio/{episode}/host/{identity}.mp4")
    return [write(artifacts / "host_manifest.json", {"generated": True, "media": record,
        "mode": mode, "audio_sha256": ref["sha256"], "segments": segments,
        "lip_sync": "speech_driven_requires_visual_review", "loop": False})]


def host_segments(timing, max_ms=30000):
    """Split on word or sentence boundaries inside the driver's face-safe duration.

    A preset talking-head stays face-forward for about four seconds. Longer
    references step back to a wide shot, and Act-Two then reports that it found
    no face. Custom-avatar jobs may still use the 30 second bound.
    """
    total = float(timing["duration_ms"])
    if total < 3000:
        raise ValueError("Speech-driven host needs at least three seconds")
    points = [float(s["startMs"]) for s in timing["sentences"]]
    points += [float(word["endMs"]) for word in timing.get("captions") or []]
    points = sorted(set(points))
    limit = float(max_ms)
    # A four-second face window can miss the nearest word by a few hundred
    # milliseconds when a pause sits on the boundary. Staying under five
    # seconds keeps a preset driver face-forward. The thirty-second path
    # already has room, so it does not take that slack.
    slop = 500.0 if limit <= 6000 else 0.0
    cuts, cursor = [], 0.0
    while total - cursor > limit + slop:
        candidates = [value for value in points
                      if 3000 <= value - cursor <= limit + slop and total - value >= 3000]
        if not candidates:
            raise ValueError("No word boundary inside the driver duration; shorten the narration segment")
        inside = [value for value in candidates if value - cursor <= limit]
        end = max(inside) if inside else min(candidates)
        cuts.append((cursor, end))
        cursor = end
    cuts.append((cursor, total))
    return cuts


def validate_driver_audio(video, narration, start_ms, end_ms):
    """Check that a filmed driver carries the selected audio, not a different take.

    Correlation tolerates AAC compression, but not a replacement performance.
    This checks audio identity/timing, not whether visible lips are convincing.
    """
    import numpy as np
    def pcm(path, offset=0, seconds=None):
        cmd = ["ffmpeg", "-v", "error", "-ss", str(offset), "-i", str(path)]
        if seconds is not None:
            cmd += ["-t", str(seconds)]
        result = subprocess.run(cmd + ["-vn", "-ar", "16000", "-ac", "1", "-f", "f32le", "pipe:1"], check=True, capture_output=True, timeout=120)
        return np.frombuffer(result.stdout, dtype="<f4")
    source, driver = pcm(narration, start_ms / 1000, (end_ms - start_ms) / 1000), pcm(video)
    length = min(len(source), len(driver))
    if length < 16000 or abs(len(source) - len(driver)) > 1280:
        raise ValueError("Driving audio missing or duration differs")
    similarity = float(np.corrcoef(source[:length], driver[:length])[0, 1])
    if not math.isfinite(similarity) or similarity < .9:
        raise ValueError("Driving performance audio does not match the selected narration at zero offset")


def sound_cue(path):
    """A short, quiet reveal cue synthesized locally; no music provider needed."""
    import array
    rng, rate = random.Random(42), 48000
    samples = array.array("h")
    for i in range(int(.18 * rate)):
        t = i / rate
        envelope = math.sin(math.pi * t / .18) ** 2
        samples.append(int(9000 * envelope * (.3 * rng.uniform(-1, 1) + .7 * math.sin(2 * math.pi * (650 - 350 * t / .18) * t))))
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(samples.tobytes())


def mix_audio(narration, output, duration_ms, cue_times):
    """Bake a final master with ducked cues; original narration remains untouched."""
    output.parent.mkdir(parents=True, exist_ok=True)
    if not cue_times:
        shutil.copyfile(narration, output)
        return output
    cue = output.with_name("reveal-cue.wav")
    sound_cue(cue)
    cmd = ["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(narration)]
    for _ in cue_times:
        cmd += ["-i", str(cue)]
    filters = ["[0:a]asplit=2[voice][control]"]
    for i, milliseconds in enumerate(cue_times, 1):
        filters.append(f"[{i}:a]volume=0.16,adelay={round(milliseconds)}:all=1[s{i}]")
    filters += ["".join(f"[s{i}]" for i in range(1, len(cue_times) + 1)) + f"amix=inputs={len(cue_times)}:normalize=0[effects]",
                "[effects][control]sidechaincompress=threshold=0.025:ratio=8:attack=5:release=120[ducked]",
                "[voice][ducked]amix=inputs=2:normalize=0,alimiter=limit=0.95:latency=1[mix]"]
    subprocess.run(cmd + ["-filter_complex", ";".join(filters), "-map", "[mix]", "-t", str(duration_ms / 1000),
                          "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(output)], check=True, timeout=180)
    return output


def run_assembly(root, episode, request, key):
    artifacts, work = paths(root, episode)
    script, plan = read(artifacts / "canonical_script.json"), read(artifacts / "visual_plan.json")
    audio, ref = selected_audio(artifacts, work / "assembly")
    timing = validate_alignment(artifacts, script, ref["sha256"])
    assets, host = read(artifacts / "assets_manifest.json"), read(artifacts / "host_manifest.json")
    if assets["script_sha256"] != editorial.sha(script) or assets["visual_plan_sha256"] != editorial.sha(plan):
        raise ValueError("Visual assets are stale")
    if host.get("generated") and host.get("audio_sha256") != ref["sha256"]:
        raise ValueError("Host was generated for a different narration")
    target = work / "assembly" / "host.mp4"
    media_store.fetch((host.get("media") or host["plate"])["key"], target)
    public = Path(root) / "remotion/public/canonical-assets"
    public.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(target, public / "host.mp4")
    prepared = []
    for shot in assets["shots"]:
        item = {"shot_id": shot["shot_id"], "beat_id": shot["shot_id"], "role": "", "text": "", "citations": [], "still": "",
                "visual_type": shot["visual_type"], "screen_text": shot.get("screen_text", ""),
                "source_label": str(shot.get("source_label") or ""), "chart": shot.get("chart"),
                "sentence_ids": shot["sentence_ids"]}
        if shot.get("media"):
            media = shot["media"]
            suffix = ".mp4" if media.get("kind") == "video" else ".png"
            local = public / (shot["shot_id"] + suffix)
            fetched = media_store.fetch(media["key"], local)
            if fetched["sha256"] != media["sha256"]:
                raise ValueError("Visual asset checksum mismatch")
            item["inset_video" if suffix == ".mp4" else "still"] = f"canonical-assets/{local.name}"
            item["playback_rate"] = max(.5, min(3, float(media.get("playback_rate", 1))))
            if shot["visual_type"] == "source":
                item["source_label"] = media["credit"]
        prepared.append(item)
    import reel_direction
    directed = reel_direction.direct_picture(prepared, timing)
    beats = []
    for item in directed:
        start, end = item.pop("start_ms"), item.pop("end_ms")
        item["from"] = round(start * .03)
        item["duration"] = max(1, round(end * .03) - item["from"])
        beats.append(item)
    mix = mix_audio(audio, work / "assembly/mixed.wav", timing["duration_ms"],
                    [b["from"] / .03 for b in beats if b["screen_text"]][:4]
                    if (request.get("production") or {}).get("sound_design", not opportunity.is_brief(request)) else [])
    shutil.copyfile(mix, public / "voice.wav")
    brief = opportunity.is_brief(request)
    payload = {"title": script["title"], "format": opportunity.FORMAT if brief else "satoshi_reel",
               "company": opportunity.context(request)["company"] if brief else "",
               "host": "canonical-assets/host.mp4", "voice": "canonical-assets/voice.wav",
               "loop_host": bool(host.get("loop")), "captions": timing["captions"], "beats": beats,
               "fps": 30, "width": 1920 if brief else 1080, "height": 1080 if brief else 1920,
               "duration_frames": math.ceil(timing["duration_ms"] * .03)}
    write(Path(root) / "remotion/public/canonical-episode.json", payload)
    write(work / "assembly/remotion-episode.json", payload)
    video = production.render_reel()  # guard remuxes the mixed master, preserving cues
    media = media_store.persist(video, f"satoshi-studio/{episode}/renders/{alignment.file_sha(video)}.mp4")
    inputs = {"request_sha256": editorial.sha(request), "script_sha256": editorial.sha(script), "audio_sha256": ref["sha256"],
              "alignment_sha256": editorial.sha(timing), "assets_sha256": editorial.sha(assets), "host_sha256": editorial.sha(host),
              "visual_plan_sha256": editorial.sha(plan)}
    outputs = [write(artifacts / "assembly_manifest.json", {**inputs, "format": payload["format"], "final_media": media, "lip_sync": host["lip_sync"],
        "mixed_audio_sha256": alignment.file_sha(mix), "status": "rendered_requires_review",
        "review": {"text_readability": "pending", "mouth_alignment": "pending", "evidence_accuracy": "pending"}})]
    if brief:
        outputs.append(write(artifacts / "outreach_draft.json",
                             opportunity.outreach_draft(script, request, media["url"])))
    return outputs


def run_publish(root, episode, request, key):
    if opportunity.is_brief(request):
        raise ValueError("Opportunity Brief is for reviewed direct outreach; Instagram publishing is disabled")
    artifacts, work = paths(root, episode)
    assembly = read(artifacts / "assembly_manifest.json")
    script = read(artifacts / "canonical_script.json")
    verdict = read(artifacts / "audio_evaluation.json")
    if verdict.get("regenerate"):
        raise ValueError("Audio requires regeneration")
    expected = {"request_sha256": editorial.sha(request), "script_sha256": editorial.sha(script),
                "audio_sha256": verdict["selected_audio"]["sha256"]}
    for filename, field in [("narration_alignment.json", "alignment_sha256"), ("assets_manifest.json", "assets_sha256"),
                             ("host_manifest.json", "host_sha256"), ("visual_plan.json", "visual_plan_sha256")]:
        expected[field] = editorial.sha(read(artifacts / filename))
    if any(assembly.get(k) != v for k, v in expected.items()):
        raise ValueError("Assembly is stale; render current artifacts before publishing")
    # The UI dispatch confirmation is the human publishing action. Module state
    # must separately record approval of the render; needs_review is not approval.
    manifest = read(Path(root) / "studio/episodes" / episode / "episode_manifest.json")
    if manifest["modules"]["assembly"]["status"] != "approved":
        raise ValueError("Approve the rendered assembly before publishing")
    if assembly["lip_sync"] == "not_applied" and not (request.get("production") or {}).get("allow_background_host_publish", False):
        raise ValueError("Background host has no lip sync; choose a speech-driven host or explicitly allow background-host publishing")
    production_id = production.episode_id(request)
    publish_root = work / "publish" / production_id
    write(publish_root / "request.json", request)
    media = assembly["final_media"]
    video = publish_root / "final.mp4"
    media_store.fetch(media["key"], video)
    if alignment.file_sha(video) != media["sha256"]:
        raise ValueError("Rendered video checksum mismatch")
    story = {"title": script["title"], "beats": [{"spoken_text": s["text"], "citations": s.get("citations", [])} for s in script["script"]]}
    distribution = distribution_enrichment.build(story, live=True)
    distribution["episode_id"] = production_id
    write(publish_root / "distribution.json", distribution)
    # Restore the durable publication ledger across independent Action jobs.
    ledger_key = f"satoshi-studio/{episode}/publish/instagram-posts.sqlite"
    import os
    client = media_store._client()
    try:
        client.head_object(Bucket=os.environ["R2_BUCKET"], Key=ledger_key)
    except Exception as exc:
        if (getattr(exc, "response", {}).get("Error") or {}).get("Code") not in {"404", "NoSuchKey", "NotFound"}:
            raise
    else:
        media_store.fetch(ledger_key, publish_root / "instagram-posts.sqlite")
    try:
        packet = lipsync.publish_final_with_distribution(publish_root, story, video, media)
    finally:
        ledger = publish_root / "instagram-posts.sqlite"
        if ledger.exists():
            media_store.persist(ledger, ledger_key)
    import canonical_instagram_permalink
    canonical_instagram_permalink.enrich_file(publish_root / "instagram.json")
    packet = read(publish_root / "instagram.json")
    return [write(artifacts / "distribution.json", packet)]
