"""Canonical resumable Satoshi Studio production orchestrator.

Initial stabilization scaffold: determines resume point and enforces the paid-host
reuse guard. Provider/module adapters will be migrated behind this runner without
changing the state contract defined in production_state.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from studio.production_state import ProductionManifest, StageState, Artifact


def load_manifest(path: Path) -> ProductionManifest:
    raw = json.loads(path.read_text())
    stages = {}
    for name, state in raw.get("stages", {}).items():
        artifacts = [Artifact(**a) for a in state.get("artifacts", [])]
        stages[name] = StageState(
            status=state.get("status", "pending"),
            artifacts=artifacts,
            attempts=state.get("attempts", 0),
            error=state.get("error"),
        )
    return ProductionManifest(
        schema_version=raw.get("schema_version", 2),
        episode_id=raw["episode_id"],
        production_id=raw["production_id"],
        publish_instagram=raw.get("publish_instagram", False),
        status=raw.get("status", "running"),
        stages=stages,
        outputs=raw.get("outputs", {}),
    )


def save_manifest(path: Path, manifest: ProductionManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    tmp.replace(path)


def plan_resume(manifest: ProductionManifest) -> dict:
    return {
        "production_id": manifest.production_id,
        "next_stage": manifest.first_incomplete_stage(),
        "status": manifest.status,
        "final_mp4_url": manifest.outputs.get("public_preview_url"),
        "instagram_permalink": manifest.outputs.get("instagram_permalink"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force-regenerate-host", action="store_true")
    args = parser.parse_args()

    path = Path(args.manifest)
    manifest = load_manifest(path)
    plan = plan_resume(manifest)

    # Safety contract: merely resuming a production never regenerates a valid
    # expensive host. A future provider adapter must require this explicit flag
    # in addition to media-spend authorization before invalidating host state.
    if args.force_regenerate_host:
        plan["force_regenerate_host"] = True
    else:
        plan["force_regenerate_host"] = False

    print(json.dumps(plan, indent=2))
    if args.plan_only:
        return 0

    # The migration PR will wire existing module_runner stages here. Until that
    # adapter is complete, fail closed rather than accidentally invoking paid
    # providers through the legacy workflow.
    raise RuntimeError(
        "Transactional runner adapters are not yet migrated; use --plan-only. "
        "Do not fall back to paid legacy execution automatically."
    )


if __name__ == "__main__":
    raise SystemExit(main())
