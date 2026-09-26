"""Sequential multi-agent runtime for adaptive long-form Satoshi episodes.

Producer and speaking agents are separate inference calls with separate prompts.
Monologue mode never instantiates a counterpart. All outputs remain review_required.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

import narrative_engine
from studio import digest
from writer import reserve

ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.environ.get("OPENAI_PODCAST_MODEL", "gpt-5.6-sol")

PRODUCER_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["next_agent", "turn_function", "objective", "evidence_target", "reason", "return_to"],
    "properties": {
        "next_agent": {"type": "string", "enum": ["satoshi", "counterpart"]},
        "turn_function": {"type": "string", "enum": sorted(narrative_engine.TURN_FUNCTIONS)},
        "objective": {"type": "string"},
        "evidence_target": {"type": "array", "items": {"type": "string"}},
        "reason": {"type": "string"},
        "return_to": {"type": "string"},
    },
}
TURN_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["text", "claim_ids", "source_ids", "thread_id"],
    "properties": {
        "text": {"type": "string"},
        "claim_ids": {"type": "array", "items": {"type": "string"}},
        "source_ids": {"type": "array", "items": {"type": "string"}},
        "thread_id": {"type": "string"},
    },
}


def call_json(model, instructions, payload, schema, credential):
    body = {
        "model": model,
        "store": False,
        "instructions": instructions,
        "input": json.dumps(payload, ensure_ascii=False),
        "max_output_tokens": 1200,
        "text": {"format": {"type": "json_schema", "name": "agent_output",
                            "strict": True, "schema": schema}},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + credential,
                 "Content-Type": "application/json"}, method="POST")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=120) as response:
            result = json.loads(response.read(2_000_000))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        raise RuntimeError("Agent request failed or outcome is unknown; no automatic retry") from None
    if result.get("status") != "completed":
        raise ValueError("Agent response incomplete or refused")
    text = "".join(
        part.get("text", "")
        for item in result.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    )
    if not text:
        raise ValueError("Agent returned no structured text")
    return json.loads(text), result.get("usage", {}), result.get("id")


def producer_instructions(mode):
    extra = (
        "In monologue mode, next_agent must always be satoshi. "
        if mode == "monologue" else
        "Choose between satoshi and counterpart only when the second voice contributes a real role."
    )
    return (
        "You are an invisible podcast producer/controller, not a speaking character. "
        "Choose exactly one next rhetorical move. Prefer intellectual movement over chatter. "
        "Prevent repetitive agreement, unsupported escalation, topic drift, and over-explanation. "
        "Surface the strongest supported counterargument when useful. Do not invent evidence. "
        + extra
    )


def satoshi_instructions():
    return (
        "You are Satoshi Shkreli, an original skeptical, witty men's-health host. "
        "Write only the next spoken turn requested by the producer. Be concise, responsive, "
        "and audience-oriented. Use original humor. Do not imitate any real presenter. "
        "Do not add factual claims outside the supplied evidence IDs and source IDs. "
        "Questions may be provocative but must not smuggle in unsupported premises."
    )


def counterpart_instructions(config):
    return (
        "You are the episode counterpart. Stay inside this role specification: "
        + json.dumps(config, ensure_ascii=False)
        + " Write only the next spoken turn requested by the producer. "
        "Respond to Satoshi rather than delivering a lecture. Preserve uncertainty. "
        "Do not invent personal experience, interviews, motives, or facts outside supplied evidence."
    )


def _allowed_ids(evidence):
    claims = {str(x.get("id")) for x in evidence.get("claims", []) if x.get("id")}
    sources = {str(x.get("id")) for x in evidence.get("sources", []) if x.get("id")}
    return claims, sources


def validate_turn_evidence(turn, evidence):
    claims, sources = _allowed_ids(evidence)
    if any(x not in claims for x in turn["claim_ids"]):
        raise ValueError("Turn cites unknown claim")
    if any(x not in sources for x in turn["source_ids"]):
        raise ValueError("Turn cites unknown source")
    return turn


def run_episode(config, evidence, episode_id, question, output_dir, model=DEFAULT_MODEL,
                max_turns=24, max_usd_per_episode=5.0, max_usd_per_call=0.25,
                live=False, request=call_json):
    narrative_engine.validate_agent_config(config)
    if not isinstance(max_turns, int) or not 1 <= max_turns <= 100:
        raise ValueError("max_turns must be 1-100")
    if not all(math.isfinite(v) and v > 0 for v in (max_usd_per_episode, max_usd_per_call)):
        raise ValueError("positive finite budgets required")

    plan = narrative_engine.default_episode_plan(question)
    state = narrative_engine.initial_state(episode_id, config["presentation_mode"], question, plan)
    root = Path(output_dir) / episode_id
    root.mkdir(parents=True, exist_ok=True)
    narrative_engine.write_json(root / "agent-config.json", config)
    narrative_engine.write_json(root / "episode-plan.json", plan)

    if not live:
        return {
            "status": "ready_for_configured_live_call",
            "mode": config["presentation_mode"],
            "model": model,
            "max_turns": max_turns,
            "publishable": False,
            "path": str(root),
        }
    if os.environ.get("OPENAI_LIVE_ENABLED") != "true":
        raise ValueError("OPENAI_LIVE_ENABLED must be true")
    credential = os.environ.get("OPENAI_API_KEY")
    if not credential:
        raise ValueError("OPENAI_API_KEY missing")

    ledger_path = root / "ledger.sqlite"
    producer_log = root / "producer-decisions.jsonl"
    turns_log = root / "turns.jsonl"

    with sqlite3.connect(ledger_path) as db:
        for index in range(1, max_turns + 1):
            context = {
                "episode_question": question,
                "presentation_mode": config["presentation_mode"],
                "evidence": evidence,
                "state": state,
                "remaining_turns": max_turns - index + 1,
            }
            call_key = digest({"episode": episode_id, "kind": "producer", "turn": index, "state": state})
            reserve(db, call_key, max_usd_per_call, max_usd_per_episode)
            decision, _, producer_id = request(
                model, producer_instructions(config["presentation_mode"]),
                context, PRODUCER_SCHEMA, credential)
            narrative_engine.validate_producer_decision(decision, config["presentation_mode"])
            producer_log.open("a", encoding="utf-8").write(
                json.dumps({"turn": index, "provider_id": producer_id, **decision}) + "\n")

            speaker = decision["next_agent"]
            if speaker == "counterpart" and config["counterpart"] is None:
                raise ValueError("Producer selected counterpart without counterpart config")
            instructions = satoshi_instructions() if speaker == "satoshi" else counterpart_instructions(
                config["counterpart"])
            turn_payload = {
                "episode_question": question,
                "role": config["satoshi"] if speaker == "satoshi" else config["counterpart"],
                "producer_decision": decision,
                "evidence": evidence,
                "conversation_so_far": state["turns"],
            }
            call_key = digest({"episode": episode_id, "kind": speaker, "turn": index, "state": state})
            reserve(db, call_key, max_usd_per_call, max_usd_per_episode)
            out, _, speaker_id = request(model, instructions, turn_payload, TURN_SCHEMA, credential)
            validate_turn_evidence(out, evidence)
            turn = {
                "turn_id": f"T{index:03d}",
                "speaker": speaker,
                "function": decision["turn_function"],
                "text": out["text"],
                "responds_to": state["turns"][-1]["turn_id"] if state["turns"] else None,
                "claim_ids": out["claim_ids"],
                "source_ids": out["source_ids"],
                "thread_id": out["thread_id"],
            }
            narrative_engine.validate_turn(turn)
            state = narrative_engine.append_turn(state, turn)
            turns_log.open("a", encoding="utf-8").write(
                json.dumps({"provider_id": speaker_id, **turn}) + "\n")
            narrative_engine.write_json(root / "conversation-state.json", state)

            if decision["turn_function"] == "resolution" and index >= 4:
                break

    state["status"] = "review_required"
    narrative_engine.write_json(root / "conversation-state.json", state)
    transcript = "# REVIEW REQUIRED\n\n"
    for turn in state["turns"]:
        transcript += f"**{turn['speaker'].upper()}**: {turn['text']}\n\n"
    (root / "draft-transcript.md").write_text(transcript, encoding="utf-8")
    (root / "REVIEW_REQUIRED.txt").write_text(
        "Synthetic draft. Verify factual support, persona boundaries and narrative quality before audio generation.\n",
        encoding="utf-8")
    return {"status": "review_required", "path": str(root), "turns": len(state["turns"]),
            "publishable": False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--episode-id", required=True)
    p.add_argument("--question", required=True)
    p.add_argument("--output", default="outputs/podcast-agentic")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--max-turns", type=int, default=24)
    p.add_argument("--budget-usd", type=float, default=5.0)
    p.add_argument("--max-usd-per-call", type=float, default=0.25)
    p.add_argument("--live", action="store_true")
    args = p.parse_args()
    result = run_episode(
        narrative_engine.load_json(args.config), narrative_engine.load_json(args.evidence),
        args.episode_id, args.question, args.output, args.model, args.max_turns,
        args.budget_usd, args.max_usd_per_call, args.live)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
