"""Validate the single-source rhetoric policy and derived mechanics provenance."""
from __future__ import annotations

import json
from pathlib import Path

POLICY_PATH = Path(__file__).with_name("rhetoric_source_policy.json")
MECHANICS_PATH = Path(__file__).with_name("curated_mechanics.json")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def validate_policy(policy):
    if policy.get("source_policy") != "single_source":
        raise ValueError("Rhetoric source policy must remain single_source")
    source = policy.get("canonical_source") or {}
    if source.get("name") != "Huberman Lab solo episodes":
        raise ValueError("Canonical rhetoric source must be Huberman Lab solo episodes")
    if source.get("allowed_content") != ["solo_explanatory_episode"]:
        raise ValueError("Only solo explanatory episodes may be source material")
    rules = policy.get("runtime_rules") or {}
    required_false = ("raw_transcript_in_prompt", "creator_specific_phrasing_in_prompt", "creator_voice_imitation")
    for key in required_false:
        if rules.get(key) is not False:
            raise ValueError(f"{key} must remain false")
    required_true = ("derived_mechanics_only", "facts_from_current_episode_research", "satoshi_persona_separate")
    for key in required_true:
        if rules.get(key) is not True:
            raise ValueError(f"{key} must remain true")
    return policy


def validate_mechanics_library(library, *, require_promoted_provenance=False):
    entries = library.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("Mechanics library needs entries")
    for entry in entries:
        if not isinstance(entry.get("mechanic"), str) or not entry["mechanic"].strip():
            raise ValueError("Each mechanic needs a neutralized description")
        provenance = entry.get("provenance")
        if require_promoted_provenance:
            if not isinstance(provenance, dict):
                raise ValueError(f"{entry.get('id')} lacks provenance")
            if provenance.get("source_family") != "huberman_lab_solo":
                raise ValueError(f"{entry.get('id')} has a noncanonical source")
            episode_ids = provenance.get("episode_ids")
            if not isinstance(episode_ids, list) or not episode_ids:
                raise ValueError(f"{entry.get('id')} lacks source episode IDs")
            if provenance.get("contains_source_prose") is not False:
                raise ValueError(f"{entry.get('id')} must not contain source prose")
    return library


def production_ready(policy_path=POLICY_PATH, mechanics_path=MECHANICS_PATH):
    policy = validate_policy(load_json(Path(policy_path)))
    library = validate_mechanics_library(load_json(Path(mechanics_path)), require_promoted_provenance=True)
    distinct = set()
    for entry in library["entries"]:
        distinct.update(entry["provenance"]["episode_ids"])
    minimum = policy["promotion_requirements"]["minimum_distinct_solo_episodes"]
    return {
        "ready": len(distinct) >= minimum,
        "distinct_source_episodes": len(distinct),
        "minimum_required": minimum,
        "reason": "ready" if len(distinct) >= minimum else "insufficient_validated_source_episodes",
    }


def main():
    policy = validate_policy(load_json(POLICY_PATH))
    library = validate_mechanics_library(load_json(MECHANICS_PATH), require_promoted_provenance=False)
    result = {
        "policy": "valid",
        "canonical_source": policy["canonical_source"]["name"],
        "mechanics_entries": len(library["entries"]),
        "production_status": "bootstrap_only_until_provenance_is_added_and_benchmark_passes",
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
