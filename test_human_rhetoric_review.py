import csv
import json
from pathlib import Path

from human_rhetoric_review import build_packet, packet_markdown, score_responses, write_response_template


def _benchmark():
    return {
        "arms": ["none", "semantic"],
        "trials": [
            {
                "brief_id": "B01",
                "topic": "Topic one",
                "evidence": "Evidence one",
                "baseline_script": "Baseline one",
                "semantic_script": "Semantic one",
                "judge": {"preferred": "A"},
            },
            {
                "brief_id": "B02",
                "topic": "Topic two",
                "evidence": "Evidence two",
                "baseline_script": "Baseline two",
                "semantic_script": "Semantic two",
                "judge": {"preferred": "B"},
            },
        ],
    }


def test_packet_is_blind_and_contains_both_candidates():
    packet, key = build_packet(_benchmark())
    serialized = json.dumps(packet)
    assert '"none"' not in serialized
    assert '"semantic"' not in serialized
    assert "Baseline one" in serialized
    assert "Semantic one" in serialized
    assert len(packet["trials"]) == 2
    assert len(key["trials"]) == 2
    md = packet_markdown(packet)
    assert "Candidate A" in md
    assert "Candidate B" in md
    assert "baseline" not in md.lower()
    assert "semantic" not in md.lower()


def test_response_template_and_unblinding(tmp_path: Path):
    packet, key = build_packet(_benchmark())
    responses = tmp_path / "human-responses.csv"
    write_response_template(packet, responses)

    rows = list(csv.DictReader(responses.open(encoding="utf-8")))
    assert [r["brief_id"] for r in rows] == ["B01", "B02"]

    # Choose the blind candidate that maps to semantic in each pair.
    semantic_choice = {}
    for row in key["trials"]:
        for blind, arm in row["blind_order"].items():
            if arm == "semantic":
                semantic_choice[row["brief_id"]] = blind

    with responses.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["brief_id", "preferred", "keep_watching", "intelligent_not_generic", "biotica_fit", "notes"],
        )
        writer.writeheader()
        for trial in packet["trials"]:
            writer.writerow({
                "brief_id": trial["brief_id"],
                "preferred": semantic_choice[trial["brief_id"]],
                "keep_watching": "tie",
                "intelligent_not_generic": "",
                "biotica_fit": "",
                "notes": "",
            })

    result = score_responses(key, responses)
    assert result["human_wins"]["semantic"] == 2
    assert result["human_wins"]["none"] == 0
    assert result["semantic_win_rate_excluding_ties"] == 1.0
