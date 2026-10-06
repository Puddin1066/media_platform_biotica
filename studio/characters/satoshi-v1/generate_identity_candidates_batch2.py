"""Generate Satoshi identity candidate batch 2 (SAT-CAND-009..016) and persist to R2."""
import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import media_store
import runway_operation

MANIFEST_PATH = ROOT / "studio/characters/satoshi-v1/identity_candidates_batch2.json"
JOB_ROOT = ROOT / "outputs/satoshi-character/jobs"
WORK_ROOT = ROOT / "outputs/satoshi-character/media"


def require_environment():
    required = [
        "RUNWAYML_API_SECRET", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY", "R2_BUCKET", "MEDIA_PUBLIC_BASE_URL",
    ]
    missing = [name for name in required if not (os.environ.get(name) or "").strip()]
    if missing:
        raise ValueError("Refusing paid generation; missing configuration: " + ", ".join(missing))
    if os.environ.get("RUNWAY_LIVE_ENABLED") != "true":
        raise ValueError("RUNWAY_LIVE_ENABLED must be true for live character generation")


def load_manifest():
    data = json.loads(MANIFEST_PATH.read_text())
    if data.get("phase") != "identity_candidates_batch_2":
        raise ValueError("Manifest is not batch 2")
    if data.get("human_selection_required_after_phase") is not True:
        raise ValueError("Batch 2 must stop for human selection")
    budget = data["budget"]
    estimate = float(budget["estimated_credits"])
    cap = float(budget["hard_phase_cap_credits"])
    if not (0 < estimate <= cap <= 12):
        raise ValueError("Batch 2 budget exceeds 12-credit safety ceiling")
    generation = data["generation"]
    if generation.get("output_count") != 8 or generation.get("model") != "muse_image":
        raise ValueError("Batch 2 is locked to eight Muse image candidates")
    if int(data.get("candidate_start", 0)) != 9:
        raise ValueError("Batch 2 candidate numbering must start at 9")
    return data


def request_id(manifest):
    stable = json.dumps(
        {"character_id": manifest["character_id"], "phase": manifest["phase"], "generation": manifest["generation"]},
        sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(stable).hexdigest()[:32]


def character_archive(response, job_id, work):
    urls = response.get("output", [])
    if isinstance(urls, dict):
        urls = [url for values in urls.values() if isinstance(values, list) for url in values]
    if not isinstance(urls, list):
        raise RuntimeError("Runway returned no candidate output list")
    persisted = []
    prefix = "satoshi/characters/satoshi-v1/candidates"
    for offset, url in enumerate(urls):
        if not isinstance(url, str) or urllib.parse.urlsplit(url).scheme != "https":
            continue
        candidate_number = 9 + offset
        suffix = Path(urllib.parse.urlsplit(url).path).suffix or ".png"
        target = Path(work) / f"SAT-CAND-{candidate_number:03d}{suffix}"
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=180) as source, target.open("wb") as dest:
            shutil.copyfileobj(source, dest)
        persisted.append(media_store.persist(target, f"{prefix}/{target.name}"))
    if len(persisted) != 8:
        raise RuntimeError(f"Expected 8 archived candidate images, got {len(persisted)}")
    return persisted


def main():
    require_environment()
    manifest = load_manifest()
    generation = manifest["generation"]
    request = {
        "operation": generation["operation"],
        "request_id": request_id(manifest),
        "allow_mutation": True,
        "allow_media_spend": manifest["budget"]["allow_media_spend"],
        "estimated_credits": manifest["budget"]["estimated_credits"],
        "body": {
            "model": generation["model"],
            "promptText": generation["prompt"],
            "ratio": generation["ratio"],
            "outputFormat": generation["output_format"],
            "outputCount": generation["output_count"],
        },
    }
    result = runway_operation.execute(
        request, archive=character_archive, job_root=JOB_ROOT, work_root=WORK_ROOT
    )
    summary = {
        "character_id": manifest["character_id"],
        "phase": manifest["phase"],
        "state": result["state"],
        "estimated_credits": result.get("estimated_credits"),
        "media": result.get("media", []),
        "next_action": "compare_all_16_and_select_one_canonical_identity",
    }
    out = ROOT / "outputs/satoshi-character/identity-candidates-batch2-result.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
