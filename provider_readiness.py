"""Fail-fast provider and durable-media readiness checks for GitHub Actions production."""
import argparse
import json
import os

REQUIRED = {
    "research_script": ["OPENAI_API_KEY"],
    "video_preview": [
        "OPENAI_API_KEY",
        "RUNWAYML_API_SECRET",
        "RUNWAY_AVATAR_ID",
        "R2_ACCOUNT_ID",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "R2_BUCKET",
        "MEDIA_PUBLIC_BASE_URL",
    ],
    "instagram_publish": [
        "META_ACCESS_TOKEN",
        "IG_USER_ID",
    ],
}

def check(mode):
    if mode not in REQUIRED:
        raise ValueError("Unknown readiness mode")
    missing = [name for name in REQUIRED[mode] if not os.environ.get(name)]
    return {
        "mode": mode,
        "ready": not missing,
        "missing": missing,
        "required": REQUIRED[mode],
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=REQUIRED, required=True)
    args = p.parse_args()
    result = check(args.mode)
    print(json.dumps(result))
    if not result["ready"]:
        p.exit(2, "Missing required GitHub secrets/config: " + ", ".join(result["missing"]) + "\n")

if __name__ == "__main__":
    main()
