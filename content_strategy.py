"""Sponsor-aware classification metadata for Biotica Media.

User-selected topics are authoritative. This module classifies a supplied topic
into one or more sponsor-friendly editorial pillars and exposes the audience job,
sponsor fit, and any extra evidence requirements. It does not autonomously choose
the next topic for normal production.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CONFIG = Path(__file__).parent / "content_pillars.json"


def load_config(path=CONFIG):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("pillars"), list):
        raise ValueError("Invalid content pillar configuration")
    shares = 0.0
    ids = set()
    for pillar in data["pillars"]:
        pid = pillar.get("id")
        share = pillar.get("target_share")
        if not isinstance(pid, str) or pid in ids or not isinstance(share, (int, float)):
            raise ValueError("Invalid or duplicate pillar")
        if not 0 < float(share) < 1:
            raise ValueError("Pillar target_share must be between zero and one")
        ids.add(pid)
        shares += float(share)
        if not pillar.get("sponsor_fit") or not pillar.get("audience_job"):
            raise ValueError("Each pillar requires audience and sponsor metadata")
    if abs(shares - 1.0) > 1e-9:
        raise ValueError("Pillar target shares must sum to 1.0")
    return data


def get_pillar(pillar_id, config=None):
    config = config or load_config()
    pillar = next((p for p in config["pillars"] if p["id"] == pillar_id), None)
    if pillar is None:
        raise ValueError("Unknown content pillar")
    return pillar


def brief(pillar, topic=None):
    out = {
        "topic": topic,
        "pillar": pillar["id"],
        "name": pillar["name"],
        "audience_job": pillar["audience_job"],
        "sponsor_fit": pillar["sponsor_fit"],
        "topic_examples": pillar["topic_examples"],
        "avoid": pillar["avoid"],
        "topic_authority": "user_or_explicit_upstream_input",
    }
    if pillar["id"] == "conspiracy_files":
        out["required_structure"] = pillar["required_structure"]
        out["allowed_verdicts"] = pillar["allowed_verdicts"]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "brief"))
    parser.add_argument("--pillar", help="Pillar id for a supplied topic")
    parser.add_argument("--topic", help="Authoritative topic supplied by user/upstream workflow")
    args = parser.parse_args()
    config = load_config()
    if args.command == "list":
        print(json.dumps([brief(p) for p in config["pillars"]], indent=2))
        return
    if not args.pillar or not args.topic:
        parser.error("brief requires --pillar and --topic")
    print(json.dumps(brief(get_pillar(args.pillar, config), args.topic), indent=2))


if __name__ == "__main__":
    main()
