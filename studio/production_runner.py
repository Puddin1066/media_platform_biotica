"""Canonical resumable Satoshi Studio production orchestrator.

The runner owns resume decisions and paid-host safety. It can read canonical
state from R2 or a local migration manifest. Provider adapters are intentionally
fail-closed until migrated behind this state contract.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from studio.production_state import ProductionManifest, StageState, Artifact
from studio import production_store


def manifest_from_dict(raw: dict) -> ProductionManifest:
    stages = {}
    for name, state in raw.get("stages", {}).items():
        artifacts = [Artifact(**a) for a in state.get("artifacts", [])]
        stages[name] = StageState(
            status=state.get("status", "pending"), artifacts=artifacts,
            attempts=state.get("attempts", 0), error=state.get("error"),
        )
    return ProductionManifest(
        schema_version=raw.get("schema_version", 2),
        episode_id=raw["episode_id"], production_id=raw["production_id"],
        publish_instagram=raw.get("publish_instagram", False),
        status=raw.get("status", "running"), stages=stages,
        outputs=raw.get("outputs", {}),
    )


def load_local(path: Path) -> ProductionManifest:
    return manifest_from_dict(json.loads(path.read_text()))


def save_local(path: Path, manifest: ProductionManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    tmp.replace(path)


def plan_resume(manifest: ProductionManifest) -> dict:
    return {
        "episode_id": manifest.episode_id,
        "production_id": manifest.production_id,
        "next_stage": manifest.first_incomplete_stage(),
        "status": manifest.status,
        "final_mp4_url": manifest.outputs.get("public_preview_url"),
        "instagram_permalink": manifest.outputs.get("instagram_permalink"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest")
    source.add_argument("--r2", action="store_true")
    parser.add_argument("--episode")
    parser.add_argument("--production-id")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--force-regenerate-host", action="store_true")
    parser.add_argument("--allow-media-spend", action="store_true")
    args = parser.parse_args()

    if args.r2:
        if not args.episode or not args.production_id:
            parser.error("--r2 requires --episode and --production-id")
        raw = production_store.load_manifest(args.episode, args.production_id)
        if raw is None:
            raise FileNotFoundError("No canonical R2 production manifest exists")
        manifest = manifest_from_dict(raw)
    else:
        manifest = load_local(Path(args.manifest))

    if args.force_regenerate_host and not args.allow_media_spend:
        raise PermissionError("force_regenerate_host requires explicit allow_media_spend")

    plan = plan_resume(manifest)
    plan["force_regenerate_host"] = bool(args.force_regenerate_host)
    plan["allow_media_spend"] = bool(args.allow_media_spend)
    print(json.dumps(plan, indent=2))
    if args.plan_only:
        return 0

    raise RuntimeError(
        "Transactional provider adapters are not yet migrated. Refusing to fall "
        "back to paid legacy execution automatically."
    )


if __name__ == "__main__":
    raise SystemExit(main())
