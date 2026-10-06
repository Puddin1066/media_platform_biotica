"""Generate canonical Satoshi reference pack from locked SAT-CAST-004 identity."""
import hashlib, json, os, shutil, sys, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import media_store
import runway_operation

MANIFEST = ROOT / "studio/characters/satoshi-v1/reference_pack.json"
JOB_ROOT = ROOT / "outputs/satoshi-character/reference-jobs"
WORK_ROOT = ROOT / "outputs/satoshi-character/reference-media"


def require_environment():
    required = ["RUNWAYML_API_SECRET","R2_ACCOUNT_ID","R2_ACCESS_KEY_ID","R2_SECRET_ACCESS_KEY","R2_BUCKET","MEDIA_PUBLIC_BASE_URL"]
    missing = [x for x in required if not (os.environ.get(x) or "").strip()]
    if missing:
        raise ValueError("Refusing paid generation; missing configuration: " + ", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED") != "true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true")


def stable_request_id(character_id, asset_id, prompt):
    raw = json.dumps({"character_id":character_id,"asset_id":asset_id,"prompt":prompt},sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


def archive_for(asset_id):
    def archive(response, job_id, work):
        urls = response.get("output", [])
        if isinstance(urls, dict):
            urls = [u for vals in urls.values() if isinstance(vals,list) for u in vals]
        urls = [u for u in urls if isinstance(u,str) and urllib.parse.urlsplit(u).scheme=="https"]
        if len(urls) != 1:
            raise RuntimeError(f"{asset_id}: expected exactly one output, got {len(urls)}")
        url = urls[0]
        suffix = Path(urllib.parse.urlsplit(url).path).suffix or ".png"
        target = Path(work) / f"{asset_id}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as source, target.open("wb") as dest:
            shutil.copyfileobj(source,dest)
        return [media_store.persist(target, f"satoshi/characters/satoshi-v1/references/{target.name}")]
    return archive


def main():
    require_environment()
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get("canonical_asset_id") != "SAT-CAST-004" or manifest.get("identity_status") != "locked":
        raise ValueError("Canonical Satoshi identity is not locked to SAT-CAST-004")
    if manifest["budget"]["estimated_credits"] > manifest["budget"]["hard_phase_cap_credits"] or manifest["budget"]["hard_phase_cap_credits"] > 20:
        raise ValueError("Reference-pack budget exceeds 20-credit hard ceiling")
    if len(manifest.get("shots",[])) != 8:
        raise ValueError("Reference pack must contain exactly eight shots")

    results = []
    for shot in manifest["shots"]:
        request = {
            "operation": "post_text_to_image",
            "request_id": stable_request_id(manifest["character_id"], shot["asset_id"], shot["prompt"]),
            "allow_mutation": True,
            "allow_media_spend": True,
            "estimated_credits": 2,
            "body": {
                "model": manifest["model"],
                "promptText": shot["prompt"],
                "ratio": manifest["ratio"],
                "referenceImages": [{
                    "uri": manifest["canonical_reference_url"],
                    "tag": manifest["reference_tag"]
                }]
            }
        }
        result = runway_operation.execute(
            request,
            archive=archive_for(shot["asset_id"]),
            job_root=JOB_ROOT,
            work_root=WORK_ROOT
        )
        media = result.get("media",[])
        if result.get("state") != "completed" or len(media) != 1:
            raise RuntimeError(f"{shot['asset_id']} did not complete")
        results.append({
            "asset_id": shot["asset_id"],
            "label": shot["label"],
            "state": result["state"],
            "estimated_credits": result.get("estimated_credits"),
            "media": media[0]
        })

    summary = {
        "character_id": manifest["character_id"],
        "canonical_asset_id": manifest["canonical_asset_id"],
        "phase": manifest["phase"],
        "state": "completed",
        "estimated_credits": sum(r["estimated_credits"] or 0 for r in results),
        "references": results,
        "next_action": "human_identity_drift_review_before_motion"
    }
    out = ROOT / "outputs/satoshi-character/reference-pack-result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
