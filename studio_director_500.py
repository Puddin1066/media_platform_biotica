"""A reviewable, spend-free directing packet for a 500-credit Runway minute.

The plan is deliberately separate from provider submission. The writer supplies
specific shot direction; this module decides which shots fit the credit ceiling.
"""
from __future__ import annotations

import math


def _integer(value, label, minimum=0, maximum=1000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be an integer from {minimum} to {maximum}")
    return value


def compile_packet(script, visual_plan, directions, production=None):
    production = production or {}
    seconds = _integer(production.get("target_seconds", script.get("target_seconds", 60)),
                       "target_seconds", 45, 90)
    ceiling = math.floor(500 * seconds / 60)
    if not isinstance(directions, dict):
        raise ValueError("Director directions must be an object")
    shots = visual_plan.get("shots") or []
    script_rows = script.get("script") or []
    sentence_ids = {row["sentence_id"] for row in script_rows}
    sentences = {row["sentence_id"]: row for row in script_rows}
    by_id = {shot["shot_id"]: shot for shot in shots}
    if not shots or len(by_id) != len(shots):
        raise ValueError("Visual plan needs unique shots")
    for shot in shots:
        if not set(shot.get("sentence_ids") or []) <= sentence_ids:
            raise ValueError("A visual shot references an unknown script sentence")

    hero = directions.get("hero") or {}
    duration = _integer(hero.get("seconds"), "hero.seconds", 4, 30)
    if duration > 10:
        raise ValueError("Keep the first hero scene at most 10 seconds for editorial flexibility")
    prompt = hero.get("prompt")
    if not isinstance(prompt, str) or not 40 <= len(prompt.strip()) <= 2000:
        raise ValueError("Hero needs a specific 40–2000 character visual prompt")
    if hero.get("model") != "seedance2_5" or hero.get("resolution") != "720p":
        raise ValueError("Director 500 hero uses Seedance 2.5 at 720p")
    if hero.get("native_dialogue"):
        raise ValueError("This voiceover format keeps generated dialogue out of the picture model")

    moving = directions.get("moving_shots") or []
    if not isinstance(moving, list) or len(moving) > 3:
        raise ValueError("Use at most three short moving inserts")
    seen = set()
    motion = []
    for item in moving:
        if not isinstance(item, dict) or item.get("shot_id") not in by_id or item["shot_id"] in seen:
            raise ValueError("Motion must name a unique existing shot")
        seen.add(item["shot_id"])
        source = by_id[item["shot_id"]]
        if str(source.get("type", "")).replace("_", " ") not in {
                "generated illustration", "illustration", "metaphor", "joke visual", "callback"}:
            raise ValueError("Motion is reserved for generated illustrations, not evidence or charts")
        clip_seconds = _integer(item.get("seconds"), "motion.seconds", 2, 10)
        action = item.get("prompt")
        if item.get("model") != "gen4_turbo" or not isinstance(action, str) or not 20 <= len(action.strip()) <= 1000:
            raise ValueError("Motion needs a specific Gen-4 Turbo action prompt")
        motion.append({"shot_id": item["shot_id"], "model": "gen4_turbo",
                       "seconds": clip_seconds, "credits": clip_seconds * 5,
                       "image_to_video_prompt": action.strip(),
                       "source_sentence_ids": source["sentence_ids"]})

    stills = _integer(directions.get("new_stills", 12), "new_stills", 0, 12)
    voice_and_effects = _integer(directions.get("audio_credits", 10), "audio_credits", 0, 30)
    lines = [
        {"asset": "hero", "model": "seedance2_5", "quantity": duration,
         "unit": "output seconds at 720p", "credits": duration * 30},
        {"asset": "motion", "model": "gen4_turbo", "quantity": sum(m["seconds"] for m in motion),
         "unit": "output seconds", "credits": sum(m["credits"] for m in motion)},
        {"asset": "stills", "model": "gen4_image_turbo", "quantity": stills,
         "unit": "images", "credits": stills * 2},
        {"asset": "character", "model": "gen4_image", "quantity": 1,
         "unit": "1080p image", "credits": 8},
        {"asset": "audio", "model": "allowance", "quantity": 1,
         "unit": "bounded narration and cues", "credits": voice_and_effects},
    ]
    first_pass = sum(line["credits"] for line in lines)
    reserve = ceiling - first_pass
    if reserve < max(120, math.ceil(ceiling * .2)):
        raise ValueError("First pass leaves too little reserve for a 4-second Seedance retry")
    shot_table = []
    for shot in shots:
        references = [sentences[sid] for sid in shot["sentence_ids"]]
        kind = str(shot.get("type") or "typography").replace("_", " ")
        illustrated = kind in {"generated illustration", "illustration", "metaphor", "joke visual", "callback"}
        composition = shot.get("label_requirements") or ""
        if isinstance(composition, list):
            composition = " ".join(map(str, composition))
        prompt = ("One legible editorial illustration for a phone-sized evidence window. "
                  "Visual intent: " + str(shot.get("intent") or "") + ". Composition: " +
                  str(composition) + ". The spoken context is: " +
                  " ".join(row["text"] for row in references) +
                  ". Show a concrete physical visual joke where appropriate. Keep the image free of "
                  "readable text, numbers, charts, citations and logos; those are composited in Remotion.") if illustrated else None
        shot_table.append({"shot_id": shot["shot_id"], "sentence_ids": shot["sentence_ids"],
                           "spoken_excerpt": " ".join(row["text"] for row in references),
                           "claim_ids": sorted({cid for row in references for cid in row.get("claim_ids", [])}),
                           "visual_type": kind, "illustration_prompt": prompt,
                           "source_label": shot.get("source_label"),
                           "screen_text": shot.get("screen_text"),
                           "remotion_direction": "Cut on this spoken idea; place source and caption in native layers. "
                           "Reveal the focal point before the next claim; do not fake camera speech."})
    return {"schema_version": 1, "format": "director_500_voiceover",
            "script_title": script.get("title", ""),
            "budget": {"seconds": seconds, "ceiling_credits": ceiling,
                       "first_pass_credits": first_pass, "retry_reserve_credits": reserve,
                       "ledger": lines, "excludes": ["OpenAI writing tokens", "Remotion compute",
                       "unplanned provider retries", "reference video input"]},
            "hero": {"model": "seedance2_5", "resolution": "720p", "seconds": duration,
                     "prompt": prompt.strip(), "audio": "mute generated audio; use approved master narration",
                     "character_image": "select the canonical generated Satoshi reference"},
            "moving_shots": motion,
            "shots": shot_table,
            "edit": {"master_audio": "approved existing narration",
                     "mouth_policy": "No close visible speech; cut to source and illustrations during narration",
                     "text_policy": "Remotion draws every caption, number, source and citation",
                     "shot_order": [shot["shot_id"] for shot in shots],
                     "opening": "Begin with the question and a visual event in the first three seconds",
                     "callback": directions.get("callback") or "Return to the opening visual in the closing beat"},
            "review": {"status": "pending", "requires": ["script and source check",
                      "hero image selection", "prompt and ledger approval"]}}
