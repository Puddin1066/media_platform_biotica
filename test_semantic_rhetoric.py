import json
from pathlib import Path

import semantic_rhetoric as sr


def _doc(episode_id, mechanics):
    return {
        "episode_id": episode_id,
        "source_text_included": False,
        "creator_voice_imitation": False,
        "mechanics": mechanics,
    }


def _m(function, mechanic):
    return {
        "function": function,
        "mechanic": mechanic,
        "when_to_use": "when useful",
        "avoid": "avoid overuse",
    }


def test_load_mechanics_preserves_provenance(tmp_path: Path):
    doc = _doc("episode-a", [_m("hook", "lead with the contradiction")])
    (tmp_path / "a.mechanics.json").write_text(json.dumps(doc), encoding="utf-8")
    rows = sr.load_mechanics(tmp_path)
    assert rows[0]["episode_id"] == "episode-a"
    assert rows[0]["mechanic_index"] == 0


def test_load_mechanics_rejects_unsafe_source_text(tmp_path: Path):
    doc = _doc("episode-a", [_m("hook", "lead with the contradiction")])
    doc["source_text_included"] = True
    (tmp_path / "a.mechanics.json").write_text(json.dumps(doc), encoding="utf-8")
    try:
        sr.load_mechanics(tmp_path)
        assert False, "expected unsafe document rejection"
    except ValueError:
        pass


def test_cosine_identity_and_orthogonal():
    assert round(sr.cosine([1.0, 0.0], [1.0, 0.0]), 6) == 1.0
    assert round(sr.cosine([1.0, 0.0], [0.0, 1.0]), 6) == 0.0


def test_semantic_clusters_groups_close_vectors():
    index = {
        "items": [
            {"id": "M001", "embedding": [1.0, 0.0]},
            {"id": "M002", "embedding": [0.99, 0.01]},
            {"id": "M003", "embedding": [0.0, 1.0]},
        ]
    }
    clusters = sr.semantic_clusters(index, threshold=0.95)
    assert len(clusters) == 2
    assert clusters[0]["members"] == ["M001", "M002"]
