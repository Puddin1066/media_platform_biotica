"""Transactional production-state primitives for Satoshi Studio.

This module deliberately contains no provider calls. It centralizes stage ordering,
artifact integrity metadata, reuse rules, and resume decisions so orchestration can
be tested without spending OpenAI or Runway credits.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

STAGES = (
    "request", "script", "prosody", "voice", "audio_review", "alignment",
    "visual_plan", "assets", "host", "assembly", "verify", "upload",
    "publish", "complete",
)

VALID_COMPLETE = {"complete", "completed", "approved", "needs_review"}


@dataclass(frozen=True)
class Artifact:
    uri: str
    sha256: str
    production_id: str
    provider: str | None = None
    provider_job_id: str | None = None
    source_hash: str | None = None
    narration_hash: str | None = None
    reused_from_production_id: str | None = None


@dataclass
class StageState:
    status: str = "pending"
    artifacts: list[Artifact] = field(default_factory=list)
    attempts: int = 0
    error: dict[str, Any] | None = None

    @property
    def complete(self) -> bool:
        return self.status in VALID_COMPLETE


@dataclass
class ProductionManifest:
    schema_version: int
    episode_id: str
    production_id: str
    publish_instagram: bool = False
    status: str = "running"
    stages: dict[str, StageState] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    def stage(self, name: str) -> StageState:
        if name not in STAGES:
            raise KeyError(f"Unknown production stage: {name}")
        return self.stages.setdefault(name, StageState())

    def first_incomplete_stage(self, stages: Iterable[str] = STAGES[:-1]) -> str | None:
        for name in stages:
            if not self.stage(name).complete:
                return name
        return None

    def host_reusable(self, source_hash: str, narration_hash: str) -> bool:
        host = self.stage("host")
        if not host.complete:
            return False
        return any(
            a.sha256 and a.source_hash == source_hash and a.narration_hash == narration_hash
            for a in host.artifacts
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def file_sha256(path: str | Path) -> str:
    h = sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def checksum_failure(*, shot_id: str, r2_key: str, expected: str, actual: str,
                     production_id: str, generating_stage: str,
                     safe_to_regenerate: bool) -> dict[str, Any]:
    """Return actionable integrity diagnostics rather than a generic mismatch."""
    return {
        "code": "ASSET_INTEGRITY_FAILURE",
        "shot_id": shot_id,
        "r2_key": r2_key,
        "expected_sha256": expected,
        "actual_sha256": actual,
        "production_id": production_id,
        "generating_stage": generating_stage,
        "safe_to_regenerate": safe_to_regenerate,
    }
