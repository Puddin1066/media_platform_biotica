"""Adapters from existing Studio artifacts/modules into transactional production.

The adapter deliberately separates reuse/import from execution. Importing a valid
legacy host never calls Runway. Paid host execution requires both explicit spend
authorization and explicit force regeneration when a reusable host exists.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import studio_media
from studio.production_state import Artifact, ProductionManifest

ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_artifacts(episode_id: str) -> Path:
    return ROOT / "studio" / "episodes" / episode_id / "artifacts"


def import_legacy_media(manifest: ProductionManifest) -> ProductionManifest:
    """Import durable legacy media references without generating anything."""
    root = legacy_artifacts(manifest.episode_id)
    assets_path, host_path, assembly_path = root / "assets_manifest.json", root / "host_manifest.json", root / "assembly_manifest.json"

    if assets_path.exists():
        packet = _read(assets_path)
        imported = []
        for shot in packet.get("shots", []):
            media = shot.get("media") or {}
            if media.get("key") and media.get("sha256"):
                imported.append(Artifact(
                    uri=f"r2://{media['key']}", sha256=media["sha256"],
                    production_id=manifest.production_id,
                    reused_from_production_id="legacy",
                ))
        if imported:
            state = manifest.stage("assets")
            state.status, state.artifacts = "complete", imported

    if host_path.exists():
        packet = _read(host_path)
        media = packet.get("media") or packet.get("plate") or {}
        if media.get("key") and media.get("sha256"):
            state = manifest.stage("host")
            state.status = "complete"
            state.artifacts = [Artifact(
                uri=f"r2://{media['key']}", sha256=media["sha256"],
                production_id=manifest.production_id,
                provider="runway" if packet.get("generated") else "r2_plate",
                source_hash=packet.get("source_sha256"),
                narration_hash=packet.get("audio_sha256"),
                reused_from_production_id="legacy",
            )]

    if assembly_path.exists():
        packet = _read(assembly_path)
        media = packet.get("final_media") or {}
        if media.get("key") and media.get("sha256"):
            state = manifest.stage("assembly")
            state.status = "complete"
            state.artifacts = [Artifact(
                uri=f"r2://{media['key']}", sha256=media["sha256"],
                production_id=manifest.production_id,
                reused_from_production_id="legacy",
            )]
            manifest.outputs["public_preview_url"] = media.get("url")
    return manifest


def run_media_stage(manifest: ProductionManifest, stage: str, request: dict[str, Any], *,
                    api_key: str = "", allow_media_spend: bool = False,
                    force_regenerate_host: bool = False) -> list[str]:
    """Execute an existing media stage with transactional spend guards."""
    if stage not in {"assets", "host", "assembly", "publish"}:
        raise ValueError(f"Unsupported media adapter stage: {stage}")
    if stage == "host":
        existing = manifest.stage("host")
        if existing.complete and existing.artifacts and not force_regenerate_host:
            return []
        if not allow_media_spend:
            raise PermissionError("Host generation requires explicit allow_media_spend")
        if existing.complete and existing.artifacts and force_regenerate_host is not True:
            raise PermissionError("Reusable host exists; explicit force_regenerate_host required")

    runner = {
        "assets": studio_media.run_assets,
        "host": studio_media.run_host,
        "assembly": studio_media.run_assembly,
        "publish": studio_media.run_publish,
    }[stage]
    return [str(p) for p in runner(ROOT, manifest.episode_id, request, api_key)]
