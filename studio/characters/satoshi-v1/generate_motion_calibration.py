"""Generate three short Satoshi motion-calibration clips from approved still references."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import media_store
import runway_operation

MANIFEST = ROOT / "studio/characters/satoshi-v1/motion_calibration.json"
JOB_ROOT = ROOT / "outputs/satoshi-character/motion-jobs"
WORK_ROOT = ROOT / "outputs/satoshi-character/motion-media"


def require_environment():
    required = ["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing = [x for x in required if not (os.environ.get(x) or "").strip()]
    if missing:
        raise ValueError("Refusing paid generation; missing configuration: " + ", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED") != "true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")


def rid(character_id, asset_id, source_url, prompt):
    raw = json.dumps({"character_id":character_id,"asset_id":asset_id,"source_url":source_url,"prompt":prompt},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def archive_for(asset_id):
    def archive(response, job_id, work):
        urls = response.get("output", [])
        if isinstance(urls, dict):
            urls = [u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls = [u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls) != 1:
            raise RuntimeError(f"{asset_id}: expected exactly one video output, got {len(urls)}")
        url = urls[0]
        suffix = Path(urllib.parse.urlsplit(url).path).suffix or ".mp4"
        target = Path(work) / f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=300) as source, target.open("wb") as dest:
            shutil.copyfileobj(source,dest)
        return [media_store.persist(target, f"satoshi/characters/satoshi-v1/motion-tests/{target.name}")]
    return archive


def main():
    require_environment()
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("identity_status") != "locked" or manifest.get("canonical_asset_id") != "SAT-CAST-004":
        raise ValueError("Motion calibration requires locked SAT-CAST-004 identity")
    if manifest["budget"]["estimated_credits"] != 60 or manifest["budget"]["hard_phase_cap_credits"] != 60:
        raise ValueError("Motion calibration is locked to a 60-credit ceiling")
    if len(manifest.get("tests",[])) != 3:
        raise ValueError("Motion calibration requires exactly three tests")
    results = []
    for test in manifest["tests"]:
        request = {
            "operation": "post_image_to_video",
            "request_id": rid(manifest["character_id"], test["asset_id"], test["source_url"], test["prompt"]),
            "allow_mutation": True,
            "allow_media_spend": True,
            "estimated_credits": 20,
            "body": {
                "model": manifest["model"],
                "promptImage": test["source_url"],
                "promptText": test["prompt"],
                "ratio": manifest["ratio"],
                "duration": manifest["duration_seconds"]
            }
        }
        result = runway_operation.execute(
            request,
            archive=archive_for(test["asset_id"]),
            job_root=JOB_ROOT,
            work_root=WORK_ROOT
        )
        media = result.get("media",[])
        if result.get("state") != "completed" or len(media) != 1:
            raise RuntimeError(f"{test['asset_id']} did not complete")
        results.append({
            "asset_id": test["asset_id"],
            "label": test["label"],
            "source_reference": test["source_reference"],
            "state": result["state"],
            "estimated_credits": result.get("estimated_credits"),
            "media": media[0]
        })
    out = {
        "character_id": manifest["character_id"],
        "canonical_asset_id": manifest["canonical_asset_id"],
        "phase": manifest["phase"],
        "state": "completed",
        "estimated_credits": sum(r["estimated_credits"] or 0 for r in results),
        "motion_tests": results,
        "next_action": "human_motion_and_identity_review"
    }
    target = ROOT / "outputs/satoshi-character/motion-calibration-result.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
