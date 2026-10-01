from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import audio_judge
import media_store
import openai_models
import studio_media
import satoshi_editorial_pipeline as base
import studio_library as library
import studio_opportunity as opportunity

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def episode_root(episode_id):
    return ROOT / "studio" / "episodes" / episode_id


def artifact_path(episode_id, module, name=None):
    root = episode_root(episode_id) / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root / (name or f"{module}.json")


def load_manifest(episode_id):
    return read_json(episode_root(episode_id) / "episode_manifest.json")


def save_manifest(episode_id, manifest):
    return write_json(episode_root(episode_id) / "episode_manifest.json", manifest)


def mark(manifest, module, status, **extra):
    state = manifest["modules"].setdefault(module, {"version": 0})
    state["status"] = status
    if status != "failed":
        state.pop("error", None)
    state.update(extra)
    return state


def deps_satisfied(manifest, requires):
    return all(manifest["modules"].get(dep, {}).get("status") in {"completed", "approved", "needs_review"} for dep in requires)


def complete(episode_id, manifest, module, outputs):
    state = manifest["modules"].setdefault(module, {"version": 0})
    next_version = int(state.get("version") or 0) + 1
    # Archive each successful text artifact before marking this module complete.
    # A failed archive leaves the module failed so it cannot silently enter the
    # production queue with only temporary runner files.
    library.capture(ROOT, episode_id, manifest, module, next_version, outputs)
    state["version"] = next_version
    state["status"] = "needs_review" if module in {"story", "script", "audio_review", "assembly"} else "completed"
    state["outputs"] = outputs
    state.pop("error", None)

    registry = read_json(ROOT / "studio" / "modules.json")["modules"]
    by_id = {m["id"]: m for m in registry}
    dependents = {m["id"]: set(m.get("requires", [])) for m in registry}
    queue = [module]
    seen = set()
    while queue:
        changed = queue.pop(0)
        for child, requires in dependents.items():
            if child in seen or changed not in requires:
                continue
            seen.add(child)
            child_state = manifest["modules"].setdefault(child, {"version": 0})
            if int(child_state.get("version") or 0) > 0:
                child_state["status"] = "stale"
            elif deps_satisfied(manifest, by_id[child].get("requires", [])):
                child_state["status"] = "ready"
            else:
                child_state["status"] = "not_ready"
            queue.append(child)
    save_manifest(episode_id, manifest)
    library.refresh_index(ROOT)


def _parse_json_response(result):
    text = base._output_text(result)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("{"), text.rfind("}")
        if left < 0 or right <= left:
            raise ValueError("Model output was not JSON")
        return json.loads(text[left:right + 1])


def role_json_call(key, role, instructions, payload):
    """Call a model role with its configured reasoning effort.

    We intentionally do not tune temperature here. Diversity comes from explicit
    candidate briefs; judgment comes from a separate high-reasoning role.
    """
    body = {
        "model": openai_models.model_for(role),
        "store": False,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 5000,
    }
    if role == "research":
        body["tools"] = [{"type": "web_search"}]
        body["tool_choice"] = "required"
        body["include"] = ["web_search_call.action.sources"]
    reasoning = openai_models.reasoning_for(role)
    if reasoning:
        body["reasoning"] = {"effort": reasoning}
    return _parse_json_response(base._post_json(base.RESPONSES_ENDPOINT, body, key))


def compact_role_call(key, role, instructions, payload, attempts=2):
    last = None
    for attempt in range(attempts):
        try:
            suffix = " Return compact valid JSON only. Keep the response under 2500 tokens." if attempt else ""
            return role_json_call(key, role, instructions + suffix, payload)
        except Exception as exc:
            last = exc
    raise last


def run_source(episode_id, request, key, model):
    del model
    normalized = base.normalize_source(request)
    if opportunity.is_brief(request):
        normalized["opportunity"] = opportunity.context(request)
        normalized["episode_constraints"].update({"audience": "company hiring manager",
                                                   "persona": "candidate speaking as themself"})
    packet = compact_role_call(
        key,
        "classification",
        ("You are a source editor. Normalize the supplied material into factual claims, contradictions, interesting moments, humorous possibilities, evidence needs, uncertainties, and citations. Do not write a script. Preserve uncertainty and never invent sources. Return only JSON. "
         + ("For this job opportunity, preserve the company, role and decision question. Never fabricate job requirements or candidate experience." if opportunity.is_brief(request) else "")),
        normalized,
    )
    p = write_json(artifact_path(episode_id, "source", "source_packet.json"), packet)
    return [str(p.relative_to(ROOT))]


def run_research(episode_id, request, key, model):
    del model
    source = read_json(artifact_path(episode_id, "source", "source_packet.json"))
    packet = compact_role_call(
        key, "research",
        ("You are the research module for Satoshi Studio. Build a claim ledger, not a legal brief. Identify what is solid enough to say, what is actually false or materially unsupported, and what single correction would make an aggressive claim defensible. Use web search to retrieve primary publications and counterevidence. Each claim needs claim_id, status, and citations with URL, author, year, and the finding actually supported. Mark unresolved claims requires_external_verification. Do not infer proof from a URL. Do not invent citations. Return JSON with claims, strongest_evidence, counterevidence, open_questions, sources_to_verify. "
         + ("Research the company's public materials, role and decision question. Separate company statements from independent evidence and identify one credible commercial implication. Avoid unsupported claims about the company or candidate." if opportunity.is_brief(request) else "Do not inject regulatory language unless regulation is the topic.")),
        {"source": source, "opportunity": opportunity.context(request)} if opportunity.is_brief(request) else source,
    )
    p = write_json(artifact_path(episode_id, "research", "research_packet.json"), packet)
    return [str(p.relative_to(ROOT))]


def _editorial_room(key, source):
    """Different jobs get different authority and model roles."""
    return {
        "story_editor": base.editorial_agent(key, openai_models.model_for("story"), "story_editor", source),
        "scientific_skeptic": base.editorial_agent(key, openai_models.model_for("editorial_reasoning"), "scientific_skeptic", source),
        "voice_editor": base.editorial_agent(key, openai_models.model_for("script"), "voice_editor", source),
    }


def run_story(episode_id, request, key, model):
    del model
    source = read_json(artifact_path(episode_id, "source", "source_packet.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    if opportunity.is_brief(request):
        target = opportunity.context(request)
        plan = compact_role_call(
            key, "story",
            "Plan a 60–90 second professional Opportunity Brief. Demonstrate judgment on the company's real decision; do not pitch the candidate until the final sentence. Structure: precise decision, two or three sourced signals, interpretation and one practical next step, then a restrained invitation. No satire, invented access, confidential information, promises, or unsupported candidate claims. Mark where evidence ends and inference begins. Return JSON with central_question, thesis, hook, signals, interpretation, next_step, candidate_bridge, target_seconds and cuts.",
            {"opportunity": target, "source": source, "research": research,
             "target_seconds": (request.get("production") or {}).get("target_seconds", 75)})
        p = write_json(artifact_path(episode_id, "story", "story_plan.json"), plan)
        return [str(p.relative_to(ROOT))]
    payload = {"source": source, "research": research, "target_seconds": (request.get("production") or {}).get("target_seconds", 60)}
    room = _editorial_room(key, source)

    common = (
        "You are a Satoshi Story Editor. Plan a story, not a monologue. The central idea must dominate. "
        "The scientific skeptic is a veto against material falsehood only, never a co-author. Maximize surprise, implication, conceptual inversion, humor, escalation and a memorable final payoff. Preserve provocative examples when defensible. Use at most one compact epistemic boundary. Exclude regulatory framing unless regulation is the subject. End on the provocative idea, never a disclaimer. Return JSON with central_question, thesis, hook, audience_objection, escalation, key_receipt, payoff, mens_health_bridge, tone, target_seconds, cuts, one_boundary_sentence."
    )
    strategies = [
        "Candidate A: lead with the strongest counterintuitive factual receipt, then widen into the larger thesis.",
        "Candidate B: lead with the provocative conceptual inversion or analogy, then earn it with evidence.",
        "Candidate C: lead with a familiar human behavior or joke, reveal the mechanism underneath it, then land the broader implication.",
    ]
    candidates = []
    for strategy in strategies:
        candidates.append(compact_role_call(key, "story", common + " " + strategy, {"payload": payload, "editorial_room": room}))

    judgment = compact_role_call(
        key,
        "editorial_reasoning",
        "You are the senior Satoshi showrunner judging three story architectures. Do not rewrite them. Select exactly one. Score each 0-10 for novelty, hook, coherence, evidentiary defensibility, humor/voice potential, audience relevance, and payoff. Penalize disclaimer creep and generic health-content framing. A speculative but defensible idea is not a flaw. Return JSON with selected_index (0, 1, or 2), scores, rationale, fatal_issue_by_candidate.",
        {"candidates": candidates, "research": research, "editorial_room": room},
    )
    selected = int(judgment.get("selected_index", -1))
    if selected not in {0, 1, 2}:
        raise ValueError(f"Story judge returned invalid selected_index={selected}")
    plan = candidates[selected]
    plan["selection"] = {"candidate": selected, "judge_model": openai_models.model_for("editorial_reasoning")}

    room_path = write_json(artifact_path(episode_id, "story", "editorial_room.json"), room)
    candidates_path = write_json(artifact_path(episode_id, "story", "story_candidates.json"), {"candidates": candidates})
    judgment_path = write_json(artifact_path(episode_id, "story", "story_judgment.json"), judgment)
    plan_path = write_json(artifact_path(episode_id, "story", "story_plan.json"), plan)
    return [str(p.relative_to(ROOT)) for p in [plan_path, candidates_path, judgment_path, room_path]]


def script_seconds(words):
    return round(words / 2.35, 1)


def run_script(episode_id, request, key, model):
    del model
    story = read_json(artifact_path(episode_id, "story", "story_plan.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    target = int(story.get("target_seconds") or (request.get("production") or {}).get("target_seconds", 60))
    max_seconds = 90 if opportunity.is_brief(request) else max(target + 15, int(target * 1.25))
    max_words = int(max_seconds * 2.35)
    out = compact_role_call(
        key, "script",
        (f"Write a final locked 60–90 second Opportunity Brief spoken by the candidate in first person, for a hiring manager. Begin with a real business decision, cite two or three signals with claim_ids, distinguish your inference, offer one actionable next step, and end with a concise role connection. Calm, crisp, specific, natural speech. Do not invent personal experience, relationships, internal facts, or financial outcomes. No Satoshi persona or satire. Hard maximum {max_words} words. Return JSON with title, thesis, script as an array of objects with text/function/claim_ids, closing_payoff. No prose outside JSON." if opportunity.is_brief(request) else
         f"Write the final locked Satoshi monologue from this selected story plan and research. Spoken, provocative, dry, funny and intellectually aggressive while factually defensible. The episode is about the IDEA, not caveats. Use no more than one compact boundary sentence to distinguish hypothesis/mechanism from proven treatment. Do not repeat caution in later beats. Do not discuss FDA, regulation, authorization, compliance, or medical-claim boundaries unless the story plan is explicitly about regulation. Preserve memorable examples and analogies. Optimize for spoken rhythm: vary sentence length, use clean turns, underplay jokes, and put the strongest conceptual inversion in the final line. Hard maximum {max_words} words. Return JSON with title, thesis, script as an array of objects with text/function/claim_ids, closing_payoff. Do not include prose outside JSON."),
        {"story_plan": story, "research": research, "opportunity": opportunity.context(request)} if opportunity.is_brief(request) else {"story_plan": story, "research": research},
    )
    sentences = out.get("script") or []
    # Carry URLs forward from research instead of asking the writer to invent them.
    claims = {c.get("claim_id") or c.get("id"): c for c in research.get("claims", []) if isinstance(c, dict)}
    # Research may reference its source ledger by ID rather than repeat each URL.
    source_urls = {source.get("source_id") or source.get("id"): source.get("url")
                   for source in research.get("strongest_evidence", []) + research.get("sources_to_verify", [])
                   if isinstance(source, dict) and source.get("url")}

    for sentence in sentences:
        citations = []
        for claim_id in sentence.get("claim_ids", []):
            if claim_id not in claims:
                raise ValueError(f"Script references unknown claim: {claim_id}")
            claim = claims[claim_id]
            if claim.get("status") in {"requires_external_verification", "unsupported", "false"}:
                raise ValueError(f"Script uses an unresolved claim: {claim_id}")
            for source in claim.get("citations", []):
                url = source.get("url") if isinstance(source, dict) else source_urls.get(source, source)
                if isinstance(url, str) and url.startswith("https://"):
                    citations.append(url)
        sentence["citations"] = sorted(set(citations))
    if not sentences:
        raise ValueError("Script module returned no sentences")
    for i, sentence in enumerate(sentences, 1):
        sentence["sentence_id"] = f"s{i:02d}"
    text = " ".join(str(s.get("text") or "").strip() for s in sentences).strip()
    words = len(text.split())
    estimated = script_seconds(words)
    out["word_count"] = words
    out["target_seconds"] = target
    out["estimated_seconds"] = estimated
    out["duration_gate"] = "pass" if estimated <= max_seconds else "fail"
    out["model_role"] = "script"
    json_path = write_json(artifact_path(episode_id, "script", "canonical_script.json"), out)
    txt_path = artifact_path(episode_id, "script", "script.txt")
    txt_path.write_text(text + "\n", encoding="utf-8")
    outputs = [json_path, txt_path]
    if opportunity.is_brief(request):
        if target < 60 or target > 90:
            raise ValueError("Opportunity Brief target_seconds must be 60–90")
        urls = {url for s in sentences for url in s.get("citations", [])}
        if len(urls) < 2:
            raise ValueError("Opportunity Brief needs at least two distinct sourced URLs")
        outputs.append(write_json(artifact_path(episode_id, "script", "source_brief.json"),
                                  opportunity.source_brief(out, request)))
    if estimated > max_seconds:
        raise ValueError(f"Script duration gate failed: estimated {estimated}s, hard max {max_seconds}s")
    return [str(p.relative_to(ROOT)) for p in outputs]


def run_prosody(episode_id, request, key, model):
    del model
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = compact_role_call(
        key, "script",
        "The script text is immutable. For every sentence_id return only performance direction: sentence_id, emotion, pace, energy 0-1, emphasis, pause_before_ms, pause_after_ms, skepticism 0-1, amusement 0-1, direction. Never repeat or rewrite sentence text. Return JSON with global_direction and sentences. " + ("Use an authentic, restrained professional tone, without satire or announcer delivery." if opportunity.is_brief(request) else ""),
        {"sentence_ids": [{"sentence_id": s["sentence_id"], "function": s.get("function", "")} for s in script["script"]]},
    )
    ids = [s["sentence_id"] for s in script["script"]]
    got = [s.get("sentence_id") for s in prosody.get("sentences", [])]
    if ids != got:
        raise ValueError("Prosody output does not cover the locked script exactly")
    p = write_json(artifact_path(episode_id, "prosody", "performance_score.json"), prosody)
    return [str(p.relative_to(ROOT))]


def run_voice(episode_id, request, key, model):
    del model
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = read_json(artifact_path(episode_id, "prosody", "performance_score.json"))
    text = " ".join(s["text"] for s in script["script"])
    outdir = ROOT / "outputs" / "studio" / episode_id / "voice"
    outdir.mkdir(parents=True, exist_ok=True)
    tts_model = os.environ.get("SATOSHI_EDITORIAL_TTS_MODEL", base.DEFAULT_TTS_MODEL)
    voice = os.environ.get("SATOSHI_EDITORIAL_TTS_VOICE", base.DEFAULT_TTS_VOICE)
    variants = {
        "a":"Dry and intellectual. Restrained humor, deliberate pauses, low theatricality.",
        "b":"Curious and incredulous. Quicker opening, controlled variation, dry disbelief.",
        "c":"Intimate and conversational. Softer energy, meaningful pauses, relaxed payoff."
    }
    if opportunity.is_brief(request):
        variants = {"a": "Calm and clear. Warm, matter-of-fact business judgment.",
                    "b": "Conversational and curious, with unhurried evidence.",
                    "c": "Direct executive briefing, natural pauses, no theatricality."}
    refs = {}
    for name, direction in variants.items():
        target = outdir / f"take-{name}.wav"
        base.render_take(text, ("Natural American male professional narrator. Do not impersonate the candidate. " if opportunity.is_brief(request) else "Natural American male editorial narrator. Smart, skeptical, slightly amused. Never announcer-like. ") + direction, target, key, tts_model, voice)
        checksum = media_store._sha256(target)
        refs[name] = media_store.persist(target, f"satoshi-studio/{episode_id}/voice/{checksum}/take-{name}.wav")
    p = write_json(artifact_path(episode_id, "voice", "voice_manifest.json"), {"takes": refs, "model": tts_model, "voice": voice, "performance_score": prosody})
    return [str(p.relative_to(ROOT))]


def run_audio_review(episode_id, request, key, model):
    del request, model
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    prosody = read_json(artifact_path(episode_id, "prosody", "performance_score.json"))
    voice_manifest = read_json(artifact_path(episode_id, "voice", "voice_manifest.json"))
    outdir = ROOT / "outputs" / "studio" / episode_id / "audio_review"
    outdir.mkdir(parents=True, exist_ok=True)
    local = {}
    for name, ref in voice_manifest["takes"].items():
        path = outdir / f"take-{name}.wav"
        media_store.fetch(ref["key"], path)
        local[name] = path
    verdict = audio_judge.judge(local, script, prosody, key)
    # A natural performance must also say every locked word. Prefer the judge's
    # take, then test alternatives against observed audio before regenerating.
    first = verdict["selected"]
    order = [first] + [name for name in ("a", "b", "c") if name != first]
    observed_path = artifact_path(episode_id, "alignment", "alignment_observations.json")
    cached = read_json(observed_path) if observed_path.exists() else {}
    fidelity_path = artifact_path(episode_id, "audio_review", "voice_fidelity_observations.json")
    fidelity = read_json(fidelity_path) if fidelity_path.exists() else {}
    errors, chosen = {}, None
    for name in order:
        ref = voice_manifest["takes"][name]
        prior = fidelity.get(name, {})
        if prior.get("audio_sha256") == ref["sha256"] and prior.get("script_sha256") == base.sha(script):
            words = prior["words"]
        elif cached.get("audio_sha256") == ref["sha256"] and cached.get("script_sha256") == base.sha(script):
            words = cached["words"]
        else:
            words = studio_media.alignment.transcribe(local[name], script, key)
        fidelity[name] = {"words": words, "audio_sha256": ref["sha256"], "script_sha256": base.sha(script)}
        write_json(fidelity_path, fidelity)
        try:
            studio_media.alignment.align_words(script, words,
                studio_media.render_audio_guard.duration_seconds(local[name]) * 1000, ref["sha256"])
        except ValueError as exc:
            errors[name] = str(exc)
            continue
        chosen = name
        write_json(observed_path, {"words": words, "audio_sha256": ref["sha256"],
                                   "script_sha256": base.sha(script)})
        break
    if chosen is None:
        raise ValueError("No voice take matches the locked script: " + json.dumps(errors))
    verdict["selected"] = chosen
    verdict["script_fidelity"] = {"status": "pass", "rejected_takes": errors}
    if chosen != first:
        verdict["selection_reason"] += f" Take {first} failed exact script fidelity; selected faithful take {chosen}."
    verdict["selected_audio"] = voice_manifest["takes"][chosen]
    p = write_json(artifact_path(episode_id, "audio_review", "audio_evaluation.json"), verdict)
    return [str(p.relative_to(ROOT)), str(observed_path.relative_to(ROOT)), str(fidelity_path.relative_to(ROOT))]


def run_visual_plan(episode_id, request, key, model):
    del model
    script = read_json(artifact_path(episode_id, "script", "canonical_script.json"))
    research = read_json(artifact_path(episode_id, "research", "research_packet.json"))
    plan = compact_role_call(
        key, "writing",
        ("Create a restrained, readable 16:9 visual plan for a professional Opportunity Brief, tied to this immutable script. Return JSON with shots; each shot has shot_id, consecutive sentence_ids, type, intent, source_priority, label_requirements, screen_text (maximum 10 words), source_label. Cover every sentence exactly once without overlapping shots. Use native typography, host or a sourced chart with explicit numeric points, units and source_url. Evidence media must carry a supplied R2 key and credit. Never fabricate data or a media key. Do not generate illustrative images, use social clips, or imply the host personally visited the company." if opportunity.is_brief(request) else
         "Create a shot plan for this immutable script. Do not change narration. Return JSON with shots; each shot has shot_id, consecutive sentence_ids, type, intent, source_priority, label_requirements, screen_text (maximum 10 words), source_label (actual author/year when sourced). Cover every sentence exactly once without overlapping shots. Use typography/host/generated illustration by default. Use evidence only with a supplied R2 image key and credit in media. Use chart only with verified numeric points (label/value), source_url and units in chart. Never fabricate chart data or media keys. The renderer supports native typography, source images, charts and generated stills; dynamic_broll currently produces an illustration, not a generated video. Prefer host/evidence/generated illustration/chart/typography/dynamic_broll/metaphor/joke_visual/callback as appropriate. Visuals should amplify the thesis rather than add new disclaimers."),
        {"script": script, "research": research},
    )
    p = write_json(artifact_path(episode_id, "visual_plan", "visual_plan.json"), plan)
    return [str(p.relative_to(ROOT))]


def media_runner(module):
    """Adapt discrete Studio stages to shared production helpers, not a new pipeline."""
    function = getattr(studio_media, "run_" + module)
    def run(episode_id, request, key, model):
        del model
        return [str(p.relative_to(ROOT)) for p in function(ROOT, episode_id, request, key)]
    return run


run_host = media_runner("host")


RUNNERS = {
    "source": run_source,
    "research": run_research,
    "story": run_story,
    "script": run_script,
    "prosody": run_prosody,
    "voice": run_voice,
    "audio_review": run_audio_review,
    "visual_plan": run_visual_plan,
    "alignment": media_runner("alignment"),
    "assets": media_runner("assets"),
    "host": run_host,
    "assembly": media_runner("assembly"),
    "publish": media_runner("publish"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--module", required=True)
    args = ap.parse_args()
    episode_id, module = args.episode, args.module
    import re
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,120}", episode_id):
        raise ValueError("Invalid episode ID")
    manifest = load_manifest(episode_id)
    registry = {m["id"]: m for m in read_json(ROOT / "studio" / "modules.json")["modules"]}
    if module not in registry:
        raise ValueError(f"Unknown module: {module}")
    if module in {"assets", "host"} and os.environ.get("STUDIO_ALLOW_MEDIA_SPEND") != "true":
        raise ValueError(f"{module} requires explicit STUDIO_ALLOW_MEDIA_SPEND=true")
    request = read_json(ROOT / manifest["request_path"])
    if opportunity.is_brief(request) and module == "publish":
        raise ValueError("Opportunity Brief cannot be published to Instagram")
    for dep in registry[module].get("requires", []):
        status = manifest["modules"].get(dep, {}).get("status")
        if status not in {"completed", "approved", "needs_review"}:
            raise ValueError(f"{module} requires {dep}; current status={status}")
    # Preserve Studio's existing convention: a manual downstream dispatch
    # approves its reviewed dependencies. Automatic queues stop at needs_review.
    for dep in registry[module].get("requires", []):
        if manifest["modules"][dep]["status"] == "needs_review":
            mark(manifest, dep, "approved", approved_version=manifest["modules"][dep].get("version"))
    mark(manifest, module, "running")
    save_manifest(episode_id, manifest)
    key = os.environ.get("OPENAI_API_KEY", "") or os.environ.get("OPEN_API_KEY", "")
    try:
        if module in RUNNERS:
            outputs = RUNNERS[module](episode_id, request, key, None)
        else:
            raise ValueError(f"No executable runner for {module}")
        complete(episode_id, manifest, module, outputs)
    except Exception as exc:
        mark(manifest, module, "failed", error=str(exc))
        save_manifest(episode_id, manifest)
        raise
    print(json.dumps({"episode_id": episode_id, "module": module, "outputs": outputs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
