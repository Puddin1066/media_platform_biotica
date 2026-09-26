"""Canonical production object for Biotica Media episodes.

One episode object tracks a user-supplied topic through research, script, visual
planning, assets, render, review, publishing, and analytics. It coordinates
existing tools; it does not replace their specialist validation.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

STAGES = (
    "topic",
    "research",
    "script",
    "visual_plan",
    "assets",
    "render",
    "review",
    "publish_package",
    "analytics",
)


def _episode_id(topic: str) -> str:
    digest = hashlib.sha256(topic.strip().encode("utf-8")).hexdigest()[:10]
    return f"bio-{digest}"


def new_episode(topic: str, *, requested_by: str = "user") -> dict:
    """Create an episode with the supplied topic as immutable editorial intent."""
    if not isinstance(topic, str) or not topic.strip():
        raise ValueError("A non-empty topic is required")
    topic = topic.strip()
    return {
        "schema_version": 1,
        "episode_id": _episode_id(topic),
        "topic": {
            "text": topic,
            "requested_by": requested_by,
            "authoritative": True,
        },
        "classification": None,
        "research": None,
        "script": None,
        "visual_plan": None,
        "assets": None,
        "render": None,
        "review": None,
        "publish_package": None,
        "analytics": None,
        "status": "topic",
    }


def validate(episode: dict) -> dict:
    if not isinstance(episode, dict) or episode.get("schema_version") != 1:
        raise ValueError("Invalid studio episode")
    topic = episode.get("topic")
    if not isinstance(topic, dict) or not topic.get("authoritative") or \
            not isinstance(topic.get("text"), str) or not topic["text"].strip():
        raise ValueError("Episode must preserve an authoritative topic")
    if episode.get("episode_id") != _episode_id(topic["text"]):
        raise ValueError("Episode ID no longer matches authoritative topic")
    if episode.get("status") not in STAGES:
        raise ValueError("Unknown studio stage")
    for stage in STAGES[1:]:
        if stage not in episode:
            raise ValueError(f"Missing studio field: {stage}")
    return episode


def classify(episode: dict, metadata: dict) -> dict:
    """Attach audience/sponsor metadata without changing the supplied topic."""
    validate(episode)
    if not isinstance(metadata, dict) or not metadata.get("pillar"):
        raise ValueError("Classification requires a pillar")
    out = deepcopy(episode)
    original_topic = out["topic"]["text"]
    out["classification"] = deepcopy(metadata)
    if out["topic"]["text"] != original_topic:
        raise ValueError("Classification cannot alter topic")
    return out


def attach(episode: dict, stage: str, artifact: dict) -> dict:
    """Attach a specialist artifact and advance the episode to that stage.

    Stages are monotonic. Existing downstream state is not silently discarded.
    Revisions should create a new episode revision outside this helper.
    """
    validate(episode)
    if stage not in STAGES[1:]:
        raise ValueError("Attach target must be a production stage")
    if not isinstance(artifact, dict) or not artifact:
        raise ValueError("Artifact must be a non-empty object")
    current = STAGES.index(episode["status"])
    target = STAGES.index(stage)
    if target < current:
        raise ValueError("Studio stages cannot move backward")
    for required_stage in STAGES[1:target]:
        if episode.get(required_stage) is None:
            raise ValueError(f"Cannot attach {stage} before {required_stage}")
    out = deepcopy(episode)
    out[stage] = deepcopy(artifact)
    out["status"] = stage
    validate(out)
    return out


def production_summary(episode: dict) -> dict:
    validate(episode)
    completed = [stage for stage in STAGES[1:] if episode.get(stage) is not None]
    next_stage = None
    for stage in STAGES[1:]:
        if episode.get(stage) is None:
            next_stage = stage
            break
    return {
        "episode_id": episode["episode_id"],
        "topic": episode["topic"]["text"],
        "status": episode["status"],
        "completed": completed,
        "next_stage": next_stage,
        "classification": episode.get("classification"),
    }


def dumps(episode: dict) -> str:
    validate(episode)
    return json.dumps(episode, indent=2, sort_keys=True) + "\n"
