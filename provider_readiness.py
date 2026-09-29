"""Fail-fast provider and durable-media readiness checks for GitHub Actions production."""
import argparse
import json
import os

import media_store

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
        "MEDIA_PUBLIC_BASE_URL",
    ],
}


def check(mode):
    if mode not in REQUIRED:
        raise ValueError("Unknown readiness mode")
    missing = [name for name in REQUIRED[mode] if not os.environ.get(name)]
    result = {
        "mode": mode,
        "ready": not missing,
        "missing": missing,
        "required": REQUIRED[mode],
    }
    if missing:
        return result
    if "MEDIA_PUBLIC_BASE_URL" in REQUIRED[mode]:
        try:
            result["media_public_base_url"] = media_store.public_base_url()
        except ValueError as exc:
            result["ready"] = False
            result["invalid"] = {"MEDIA_PUBLIC_BASE_URL": str(exc)}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=REQUIRED, required=True)
    args = p.parse_args()
    result = check(args.mode)
    print(json.dumps(result))
    if not result["ready"]:
        parts = []
        if result.get("missing"):
            parts.append("Missing: " + ", ".join(result["missing"]))
        if result.get("invalid"):
            for name, message in result["invalid"].items():
                parts.append(f"Invalid {name}: {message}")
        p.exit(2, "Provider readiness blocked. " + " ".join(parts) + "\n")


if __name__ == "__main__":
    main()
