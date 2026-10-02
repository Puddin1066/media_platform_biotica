"""Canonical resumable Satoshi Studio production orchestrator."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from studio.production_state import ProductionManifest, StageState, Artifact
from studio import production_store, production_adapter

ROOT = Path(__file__).resolve().parents[1]


def manifest_from_dict(raw: dict) -> ProductionManifest:
    stages = {}
    for name, state in raw.get("stages", {}).items():
        artifacts = [Artifact(**a) for a in state.get("artifacts", [])]
        stages[name] = StageState(status=state.get("status", "pending"), artifacts=artifacts,
                                  attempts=state.get("attempts", 0), error=state.get("error"))
    return ProductionManifest(schema_version=raw.get("schema_version", 2), episode_id=raw["episode_id"],
        production_id=raw["production_id"], publish_instagram=raw.get("publish_instagram", False),
        status=raw.get("status", "running"), stages=stages, outputs=raw.get("outputs", {}))


def load_local(path: Path) -> ProductionManifest:
    return manifest_from_dict(json.loads(path.read_text()))


def save_local(path: Path, manifest: ProductionManifest) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(manifest.to_dict(), indent=2) + "\n")
    tmp.replace(path)


def plan_resume(manifest: ProductionManifest) -> dict:
    return {"episode_id": manifest.episode_id, "production_id": manifest.production_id,
            "next_stage": manifest.first_incomplete_stage(), "status": manifest.status,
            "final_mp4_url": manifest.outputs.get("public_preview_url"),
            "instagram_permalink": manifest.outputs.get("instagram_permalink")}


def request_for(episode_id: str) -> dict:
    path = ROOT / "studio" / "episodes" / episode_id / "request.json"
    if not path.exists():
        raise FileNotFoundError(f"Episode request missing: {path}")
    return json.loads(path.read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest")
    source.add_argument("--r2", action="store_true")
    parser.add_argument("--episode")
    parser.add_argument("--production-id")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--import-legacy", action="store_true")
    parser.add_argument("--stage", choices=["assets", "host", "assembly", "publish"])
    parser.add_argument("--force-regenerate-host", action="store_true")
    parser.add_argument("--allow-media-spend", action="store_true")
    args = parser.parse_args()

    local_path = None
    if args.r2:
        if not args.episode or not args.production_id:
            parser.error("--r2 requires --episode and --production-id")
        raw = production_store.load_manifest(args.episode, args.production_id)
        if raw is None:
            raise FileNotFoundError("No canonical R2 production manifest exists")
        manifest = manifest_from_dict(raw)
    else:
        local_path = Path(args.manifest)
        manifest = load_local(local_path)

    if args.force_regenerate_host and not args.allow_media_spend:
        raise PermissionError("force_regenerate_host requires explicit allow_media_spend")

    if args.import_legacy:
        manifest = production_adapter.import_legacy_media(manifest)
        if args.r2:
            production_store.save_manifest(manifest.to_dict())
        else:
            save_local(local_path, manifest)

    plan = plan_resume(manifest)
    plan.update(force_regenerate_host=bool(args.force_regenerate_host), allow_media_spend=bool(args.allow_media_spend))
    print(json.dumps(plan, indent=2))
    if args.plan_only or not args.stage:
        return 0

    request = request_for(manifest.episode_id)
    outputs = production_adapter.run_media_stage(
        manifest, args.stage, request, api_key=os.environ.get("OPENAI_API_KEY", ""),
        allow_media_spend=args.allow_media_spend, force_regenerate_host=args.force_regenerate_host,
    )
    state = manifest.stage(args.stage)
    state.attempts += 1
    if outputs or (args.stage == "host" and state.complete):
        state.status = "complete"
        state.error = None
    if args.stage == "assembly":
        packet_path = ROOT / "studio" / "episodes" / manifest.episode_id / "artifacts" / "assembly_manifest.json"
        if packet_path.exists():
            packet = json.loads(packet_path.read_text())
            media = packet.get("final_media") or {}
            manifest.outputs["public_preview_url"] = media.get("url")
    if args.r2:
        production_store.save_manifest(manifest.to_dict())
    else:
        save_local(local_path, manifest)
    print(json.dumps({"stage": args.stage, "outputs": outputs, **plan_resume(manifest)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
