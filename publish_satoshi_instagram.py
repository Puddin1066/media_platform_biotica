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
import urllib.error
import urllib.parse
import urllib.request
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


def assert_publicly_fetchable(url, timeout=20):
    """Require an anonymous HTTPS GET before handing the URL to Meta."""
    if urllib.parse.urlparse(url).scheme != "https":
        raise ValueError("public_video_url must be HTTPS")
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "BioticaPublish/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = getattr(response, "status", None) or response.getcode()
            if code >= 400:
                raise ValueError(f"public_video_url HEAD returned HTTP {code}")
            return code
    except urllib.error.HTTPError as exc:
        # Some public CDNs reject HEAD; fall through to a ranged GET.
        if exc.code not in (403, 405):
            raise ValueError(
                f"public_video_url is not anonymously fetchable (HTTP {exc.code}). "
                "Instagram cannot download from the R2 S3 API host; set "
                "MEDIA_PUBLIC_BASE_URL to a public r2.dev or custom domain."
            ) from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"public_video_url is unreachable: {exc}") from exc

    request = urllib.request.Request(
        url, headers={"User-Agent": "BioticaPublish/0.1", "Range": "bytes=0-0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            code = getattr(response, "status", None) or response.getcode()
            if code >= 400:
                raise ValueError(f"public_video_url GET returned HTTP {code}")
            return code
    except urllib.error.HTTPError as exc:
        raise ValueError(
            f"public_video_url is not anonymously fetchable (HTTP {exc.code}). "
            "Instagram cannot download from the R2 S3 API host; set "
            "MEDIA_PUBLIC_BASE_URL to a public r2.dev or custom domain."
        ) from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"public_video_url is unreachable: {exc}") from exc


def publish(release, ledger, token, ig_user_id, version="v25.0",
            poll_seconds=5, max_polls=36):
    """Create + poll Meta container. Default budget is ~3 minutes (5s × 36).

    Runway host generation is the slow Satoshi path; Instagram processing should
    finish in well under that. ERROR/EXPIRED fail immediately instead of burning
    the poll budget. Reject non-public media URLs before create_container.
    """
    assert_publicly_fetchable(release["public_video_url"])
    created = instagram.create_container(release, ledger, ig_user_id, token, version)
    job = created["job"]
    for attempt in range(max_polls):
        result = instagram.publish_container(job, ledger, ig_user_id, token, version)
        state = result.get("state")
        if state == "published":
            snap = instagram.insights(job, ledger, token, version)
            return {"create": created, "publish": result, "insights": snap,
                    "account": DEFAULT_ACCOUNT, "job": job}
        if state == "failed":
            raise RuntimeError(
                "Instagram container failed: "
                + json.dumps(result.get("provider_status") or result, sort_keys=True)
            )
        code = result.get("status_code") or (result.get("provider_status") or {}).get("status_code")
        print(f"instagram_container poll={attempt + 1}/{max_polls} status_code={code}",
              flush=True)
        time.sleep(poll_seconds)
    raise TimeoutError(
        f"Instagram container did not reach FINISHED/published within "
        f"{poll_seconds * max_polls}s"
    )


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
