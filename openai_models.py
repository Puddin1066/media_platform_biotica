"""Central OpenAI model selection for the Biotica Media studio.

This module contains no credentials and makes no network calls. It maps studio
jobs to configurable model roles so production code can avoid hard-coded model
names. Environment variables may override every default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRole:
    name: str
    model: str
    purpose: str
    reasoning: str | None = None


def _env(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    if not value:
        raise ValueError(f"{name} cannot be empty")
    return value


def roles() -> dict[str, ModelRole]:
    """Return the current production model policy.

    Story generation and script writing are deliberately separate roles even
    when they use the same underlying model. This lets us tune them independently
    without multiplying providers or coupling narrative exploration to compression.
    """
    return {
        "editorial_reasoning": ModelRole(
            "editorial_reasoning",
            _env("OPENAI_EDITORIAL_MODEL", "gpt-5.6-sol"),
            "hard editorial judgment, synthesis, counter-case analysis, final review",
            _env("OPENAI_EDITORIAL_REASONING", "high"),
        ),
        "research": ModelRole(
            "research",
            _env("OPENAI_RESEARCH_MODEL", "gpt-5.6-terra"),
            "web-backed research packets and evidence synthesis",
            _env("OPENAI_RESEARCH_REASONING", "medium"),
        ),
        "story": ModelRole(
            "story",
            _env("OPENAI_STORY_MODEL", _env("OPENAI_WRITING_MODEL", "gpt-5.6-terra")),
            "divergent story architecture, hooks, inversions, escalation and payoff",
            _env("OPENAI_STORY_REASONING", "medium"),
        ),
        "script": ModelRole(
            "script",
            _env("OPENAI_SCRIPT_MODEL", _env("OPENAI_WRITING_MODEL", "gpt-5.6-terra")),
            "spoken-language compression, rhythm, humor and final monologue writing",
            _env("OPENAI_SCRIPT_REASONING", "medium"),
        ),
        "writing": ModelRole(
            "writing",
            _env("OPENAI_WRITING_MODEL", "gpt-5.6-terra"),
            "general treatments, hooks, captions and derivative copy",
            _env("OPENAI_WRITING_REASONING", "medium"),
        ),
        "classification": ModelRole(
            "classification",
            _env("OPENAI_CLASSIFICATION_MODEL", "gpt-5.6-luna"),
            "high-volume tagging, routing, extraction and rhetorical labeling",
            _env("OPENAI_CLASSIFICATION_REASONING", "low"),
        ),
        "embedding": ModelRole(
            "embedding",
            _env("OPENAI_EMBED_MODEL", "text-embedding-3-small"),
            "semantic retrieval for rhetorical corpus, evidence and production memory",
        ),
    }


def model_for(role: str) -> str:
    try:
        return roles()[role].model
    except KeyError as exc:
        raise ValueError(f"Unknown OpenAI model role: {role}") from exc


def reasoning_for(role: str) -> str | None:
    try:
        return roles()[role].reasoning
    except KeyError as exc:
        raise ValueError(f"Unknown OpenAI model role: {role}") from exc


def public_config() -> dict[str, dict[str, str | None]]:
    """Safe diagnostic output: model names and purposes, never API keys."""
    return {
        key: {"model": value.model, "purpose": value.purpose, "reasoning": value.reasoning}
        for key, value in roles().items()
    }
