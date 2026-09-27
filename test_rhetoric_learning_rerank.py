import json
from pathlib import Path

from rhetoric_learning_rerank import load_human_priors, rerank


def _write(tmp_path: Path, trials):
    path = tmp_path / "history.jsonl"
    path.write_text(json.dumps({"trials": trials}) + "\n", encoding="utf-8")
    return path


def test_model_only_history_never_enables(tmp_path):
    path = _write(tmp_path, [{"human_choice": None, "retrieved_mechanics": [{"id": "M001"}]}] * 50)
    priors = load_human_priors(path)
    assert priors["enabled"] is False
    assert priors["human_trials"] == 0


def test_fewer_than_twelve_human_trials_does_not_rerank(tmp_path):
    trials = [{"human_choice": "semantic", "retrieved_mechanics": [{"id": "M001"}]} for _ in range(11)]
    priors = load_human_priors(_write(tmp_path, trials))
    assert priors["enabled"] is False
    rows = [{"id": "M002", "score": 0.51}, {"id": "M001", "score": 0.50}]
    assert [r["id"] for r in rerank(rows, priors, 2)] == ["M002", "M001"]


def test_repeated_human_wins_can_break_close_semantic_tie(tmp_path):
    trials = []
    for _ in range(12):
        trials.append({"human_choice": "semantic", "retrieved_mechanics": [{"id": "M001"}]})
    priors = load_human_priors(_write(tmp_path, trials))
    assert priors["enabled"] is True
    rows = [{"id": "M002", "score": 0.51}, {"id": "M001", "score": 0.50}]
    ranked = rerank(rows, priors, 2)
    assert ranked[0]["id"] == "M001"
    assert ranked[0]["human_prior_effect"] > 0


def test_sparse_mechanic_is_not_adjusted_even_after_global_gate(tmp_path):
    trials = [{"human_choice": "semantic", "retrieved_mechanics": [{"id": "M001"}]} for _ in range(12)]
    trials.append({"human_choice": "semantic", "retrieved_mechanics": [{"id": "M003"}]})
    priors = load_human_priors(_write(tmp_path, trials))
    rows = [{"id": "M003", "score": 0.50}]
    ranked = rerank(rows, priors, 1)
    assert ranked[0]["human_prior_effect"] == 0.0
