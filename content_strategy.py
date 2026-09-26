"""Sponsor-aware editorial planning for Biotica Media.

This module does not choose scientific conclusions. It keeps the published mix
close to the six editorial pillars while exposing sponsor-fit metadata and the
extra evidence requirements for Conspiracy Files.
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


def next_pillar(history, config=None):
    """Pick the most underrepresented pillar relative to the target mix."""
    config = config or load_config()
    counts = {p["id"]: 0 for p in config["pillars"]}
    for row in history:
        pid = row.get("pillar") if isinstance(row, dict) else None
        if pid in counts:
            counts[pid] += 1
    total_after = sum(counts.values()) + 1
    ranked = []
    for pillar in config["pillars"]:
        desired_after = pillar["target_share"] * total_after
        deficit = desired_after - counts[pillar["id"]]
        ranked.append((deficit, pillar["target_share"], pillar["id"], pillar))
    ranked.sort(reverse=True, key=lambda x: (x[0], x[1], x[2]))
    return ranked[0][3]


def brief(pillar):
    out = {
        "pillar": pillar["id"],
        "name": pillar["name"],
        "audience_job": pillar["audience_job"],
        "sponsor_fit": pillar["sponsor_fit"],
        "topic_examples": pillar["topic_examples"],
        "avoid": pillar["avoid"],
    }
    if pillar["id"] == "conspiracy_files":
        out["required_structure"] = pillar["required_structure"]
        out["allowed_verdicts"] = pillar["allowed_verdicts"]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "next"))
    parser.add_argument("--history", help="Optional JSON list of prior published items")
    args = parser.parse_args()
    config = load_config()
    if args.command == "list":
        print(json.dumps([brief(p) for p in config["pillars"]], indent=2))
        return
    history = []
    if args.history:
        history = json.loads(Path(args.history).read_text(encoding="utf-8"))
        if not isinstance(history, list):
            raise ValueError("History must be a JSON list")
    print(json.dumps(brief(next_pillar(history, config)), indent=2))


if __name__ == "__main__":
    main()
