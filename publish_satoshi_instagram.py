"""Auto-publish a finished Satoshi Reel to the configured Instagram professional account.

Policy: after a successful render + R2 persist, post to @byoticallc (IG_USER_ID).
Quality screening happens later on Instagram; this step does not wait for editorial
review. Duplicate submissions are still blocked by the instagram.py ledger.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import instagram
import release_instagram
from studio import digest

DEFAULT_ACCOUNT = "byoticallc"


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def find_public_url(video: Path, manifests):
    """Match the local reel to a persisted R2 public URL via sha256."""
    checksum = _sha_file(video)
    for manifest_path in manifests:
        data = _load_json(Path(manifest_path), {}) or {}
        for asset in data.get("assets", []):
            if asset.get("sha256") == checksum and asset.get("url", "").startswith("https://"):
                return asset["url"], asset.get("key")
            local = asset.get("local_file")
            if local and Path(local).resolve() == video.resolve() and asset.get("url", "").startswith("https://"):
                return asset["url"], asset.get("key")
    raise ValueError(
        "No public HTTPS URL for rendered reel in media manifests; persist to R2 first"
    )


def caption_from_outputs(request, draft) -> str:
    topic = (request or {}).get("topic") or (draft or {}).get("topic") or "Biotica"
    title = ((draft or {}).get("script") or {}).get("title") or topic
    lines = [
        str(title).strip()[:120],
        "",
        "Men's health inquiry — auto-posted from Satoshi pipeline. Screened later.",
        "#menshealth #biotica",
    ]
    caption = "\n".join(lines)
    return caption[:2200]


def build_auto_release(video, public_url, request, draft, footage_plan, reviewer):
    script = (draft or {}).get("script") or {}
    script_hash = digest(script) if script else _sha_file(video)
    plan_hash = digest(footage_plan) if footage_plan else script_hash
    return release_instagram.build_release(
        str(video),
        public_url,
        caption_from_outputs(request, draft),
        reviewer,
        script_hash,
        plan_hash,
    )


def publish(release, ledger, token, ig_user_id, version="v25.0",
            poll_seconds=15, max_polls=40):
    created = instagram.create_container(release, ledger, ig_user_id, token, version)
    job = created["job"]
    for _ in range(max_polls):
        result = instagram.publish_container(job, ledger, ig_user_id, token, version)
        if result.get("state") == "published":
            snap = instagram.insights(job, ledger, token, version)
            return {"create": created, "publish": result, "insights": snap,
                    "account": DEFAULT_ACCOUNT, "job": job}
        time.sleep(poll_seconds)
    raise TimeoutError("Instagram container did not reach FINISHED/published in time")


def run(video, manifests, request_path, draft_path, footage_plan_path, ledger,
        live=False, reviewer="satoshi-auto-publish"):
    video = Path(video)
    if not video.is_file():
        raise ValueError("Rendered reel is missing")
    public_url, key = find_public_url(video, manifests)
    request = _load_json(Path(request_path), {}) if request_path else {}
    draft = _load_json(Path(draft_path), {}) if draft_path else {}
    plan = _load_json(Path(footage_plan_path), {}) if footage_plan_path else {}
    release = build_auto_release(video, public_url, request, draft, plan, reviewer)
    packet = {
        "policy": "auto_publish_then_screen_on_instagram",
        "account": DEFAULT_ACCOUNT,
        "r2_key": key,
        "release": release,
        "live": bool(live),
    }
    if not live:
        packet["status"] = "dry_run_ready"
        return packet

    token = os.environ.get("META_ACCESS_TOKEN")
    user = os.environ.get("IG_USER_ID")
    if not token or not user:
        raise ValueError("META_ACCESS_TOKEN and IG_USER_ID required for live Instagram publish")
    version = os.environ.get("META_GRAPH_VERSION", "v25.0")
    Path(ledger).parent.mkdir(parents=True, exist_ok=True)
    result = publish(release, ledger, token, user, version)
    packet["status"] = "published"
    packet["result"] = result
    return packet


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--video", default="remotion/out/reel.mp4")
    p.add_argument("--manifest", action="append", default=[],
                   help="media-manifest.json from persist_media (repeatable)")
    p.add_argument("--request", default="requests/satoshi/current.json")
    p.add_argument("--draft", default="")
    p.add_argument("--footage-plan", default="outputs/video-preview/footage-plan.json")
    p.add_argument("--ledger", default="private/instagram-posts.sqlite")
    p.add_argument("--output", default="outputs/instagram/auto-publish.json")
    p.add_argument("--live", action="store_true")
    p.add_argument("--reviewer", default="satoshi-auto-publish")
    args = p.parse_args()

    draft = args.draft
    if not draft:
        root = Path("outputs/satoshi-short/produce")
        matches = sorted(root.rglob("draft.json")) if root.exists() else []
        draft = str(matches[0]) if matches else ""

    manifests = args.manifest or [
        "outputs/media-manifest.json",
        "dist/video/media-manifest.json",
    ]
    result = run(
        args.video, manifests, args.request, draft, args.footage_plan,
        args.ledger, live=args.live, reviewer=args.reviewer,
    )
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
