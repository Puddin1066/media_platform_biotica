"""Adaptive narrative-state contracts for long-form Satoshi episodes.

This module does not call a model. It defines deterministic contracts shared by
monologue and dialogue modes so speaker count is chosen by the material rather
than hard-coded into the show.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

PRESENTATION_MODES = {"monologue", "dialogue", "source_voice", "panel"}
TURN_FUNCTIONS = {
    "hook", "question", "partial_answer", "claim", "mechanism", "evidence",
    "interpretation", "challenge", "clarification", "counterexample",
    "anecdote", "analogy", "reversal", "qualification", "implication",
    "callback", "resolution", "transition",
}
SPEAKER_ROLES = {"satoshi", "counterpart"}


def validate_agent_config(config):
    if not isinstance(config, dict):
        raise ValueError("Agent config must be an object")
    required = {"presentation_mode", "satoshi", "counterpart", "producer"}
    if set(config) != required:
        raise ValueError("Invalid agent config fields")
    if config["presentation_mode"] not in PRESENTATION_MODES:
        raise ValueError("Unknown presentation mode")
    for key in ("satoshi", "producer"):
        if not isinstance(config[key], dict) or not config[key].get("role"):
            raise ValueError(f"{key} config requires a role")
    cp = config["counterpart"]
    if config["presentation_mode"] == "monologue":
        if cp is not None:
            raise ValueError("Monologue mode must not instantiate a counterpart")
    else:
        if not isinstance(cp, dict):
            raise ValueError("Non-monologue modes require counterpart config")
        required_cp = {
            "role", "expertise", "position", "evidence_allowed",
            "known_uncertainties", "communication_style",
            "relationship_to_satoshi", "prohibited_claims",
        }
        if set(cp) != required_cp:
            raise ValueError("Invalid counterpart config fields")
    return config


def validate_turn(turn):
    required = {
        "turn_id", "speaker", "function", "text", "responds_to",
        "claim_ids", "source_ids", "thread_id",
    }
    if not isinstance(turn, dict) or set(turn) != required:
        raise ValueError("Invalid turn fields")
    if turn["speaker"] not in SPEAKER_ROLES:
        raise ValueError("Unknown speaker")
    if turn["function"] not in TURN_FUNCTIONS:
        raise ValueError("Unknown turn function")
    if not isinstance(turn["text"], str) or not turn["text"].strip():
        raise ValueError("Turn text is required")
    for key in ("claim_ids", "source_ids"):
        if not isinstance(turn[key], list) or any(not isinstance(x, str) for x in turn[key]):
            raise ValueError(f"{key} must be a string list")
    if turn["responds_to"] is not None and not isinstance(turn["responds_to"], str):
        raise ValueError("responds_to must be null or a turn id")
    return turn


def validate_producer_decision(decision, mode):
    required = {
        "next_agent", "turn_function", "objective", "evidence_target",
        "reason", "return_to",
    }
    if not isinstance(decision, dict) or set(decision) != required:
        raise ValueError("Invalid producer decision fields")
    if decision["next_agent"] not in SPEAKER_ROLES:
        raise ValueError("Unknown next agent")
    if mode == "monologue" and decision["next_agent"] != "satoshi":
        raise ValueError("Monologue producer can only select Satoshi")
    if decision["turn_function"] not in TURN_FUNCTIONS:
        raise ValueError("Unknown turn function")
    for key in ("objective", "reason", "return_to"):
        if not isinstance(decision[key], str) or not decision[key].strip():
            raise ValueError(f"{key} is required")
    if not isinstance(decision["evidence_target"], list) or any(
            not isinstance(x, str) for x in decision["evidence_target"]):
        raise ValueError("evidence_target must be a string list")
    return decision


def initial_state(episode_id, presentation_mode, main_question, episode_plan):
    if presentation_mode not in PRESENTATION_MODES:
        raise ValueError("Unknown presentation mode")
    if not all(isinstance(x, str) and x.strip() for x in (episode_id, main_question)):
        raise ValueError("episode id and main question required")
    if not isinstance(episode_plan, dict):
        raise ValueError("episode plan required")
    return {
        "schema_version": 1,
        "episode_id": episode_id,
        "presentation_mode": presentation_mode,
        "current_act": 1,
        "main_question": main_question,
        "open_questions": [main_question],
        "resolved_questions": [],
        "claims_introduced": [],
        "sources_introduced": [],
        "callbacks_available": [],
        "conversation_threads": [],
        "turns": [],
        "estimated_runtime_seconds": 0,
        "episode_plan": deepcopy(episode_plan),
        "status": "planned",
        "publishable": False,
    }


def append_turn(state, turn, words_per_minute=145):
    validate_turn(turn)
    if state.get("presentation_mode") == "monologue" and turn["speaker"] != "satoshi":
        raise ValueError("Monologue state cannot accept counterpart turns")
    known = {t["turn_id"] for t in state.get("turns", [])}
    if turn["turn_id"] in known:
        raise ValueError("Duplicate turn id")
    if turn["responds_to"] is not None and turn["responds_to"] not in known:
        raise ValueError("Turn responds to unknown turn")
    state = deepcopy(state)
    state["turns"].append(turn)
    for claim_id in turn["claim_ids"]:
        if claim_id not in state["claims_introduced"]:
            state["claims_introduced"].append(claim_id)
    for source_id in turn["source_ids"]:
        if source_id not in state["sources_introduced"]:
            state["sources_introduced"].append(source_id)
    words = sum(len(t["text"].split()) for t in state["turns"])
    state["estimated_runtime_seconds"] = round(words / words_per_minute * 60)
    state["status"] = "drafting"
    return state


def default_episode_plan(question):
    """Loose map: enough structure to prevent drift, not a complete script."""
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question required")
    return {
        "opening_tension": "",
        "central_question": question.strip(),
        "initial_hypothesis": "",
        "major_evidence_development": "",
        "strongest_competing_explanation": "",
        "largest_reversal": "",
        "unresolved_uncertainty": "",
        "practical_implication": "",
        "ending_callback": "",
    }


def default_agent_config(mode="monologue", counterpart_role=None):
    satoshi = {
        "role": "satoshi",
        "function": (
            "Persistent original host: audience curiosity, skeptical questioning, "
            "mens-health consequences, evidence-aware humor and forward motion."
        ),
    }
    producer = {
        "role": "producer",
        "function": (
            "Invisible controller: choose the next rhetorical move, prevent drift, "
            "surface counterarguments, request clarification and protect evidence scope."
        ),
    }
    counterpart = None
    if mode != "monologue":
        role = counterpart_role or "evidence_reviewer"
        counterpart = {
            "role": role,
            "expertise": "",
            "position": "",
            "evidence_allowed": [],
            "known_uncertainties": [],
            "communication_style": "",
            "relationship_to_satoshi": "",
            "prohibited_claims": [],
        }
    config = {
        "presentation_mode": mode,
        "satoshi": satoshi,
        "counterpart": counterpart,
        "producer": producer,
    }
    return validate_agent_config(config)


def write_json(path, value):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
