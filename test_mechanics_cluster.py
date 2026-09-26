import json
from pathlib import Path

from mechanics_cluster import build_library, cluster


def _row(function, mechanic, episode="e1", index=0):
    return {
        "episode_id": episode,
        "mechanic_index": index,
        "function": function,
        "mechanic": mechanic,
        "when_to_use": "when useful",
        "avoid": "avoid overuse",
    }


def test_similar_mechanics_cluster_together():
    rows = [
        _row("causal explanation", "show a source to intermediate effect to outcome chain"),
        _row("causal explanation", "show source to intermediate effect to final outcome chain", "e2"),
        _row("countercase", "state the strongest alternative explanation before resolving it", "e3"),
    ]
    result = cluster(rows, threshold=0.4)
    assert len(result) == 2
    assert len(result[0]["members"]) == 2


def test_library_preserves_episode_provenance(tmp_path: Path):
    doc = {
        "episode_id": "episode-a",
        "mechanics": [{
            "function": "scope",
            "mechanic": "define the boundary before explaining the mechanism",
            "when_to_use": "before complex explanation",
            "avoid": "excessive setup",
        }],
    }
    (tmp_path / "episode-a.mechanics.json").write_text(json.dumps(doc), encoding="utf-8")
    result = build_library(tmp_path)
    assert result["mechanic_count"] == 1
    assert result["clusters"][0]["members"][0]["episode_id"] == "episode-a"
