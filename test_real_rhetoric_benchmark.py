from real_rhetoric_benchmark import (
    PERSPECTIVE_DIMENSIONS,
    REAL_EVIDENCE_BRIEFS,
    evidence_text,
    script_prompt,
)


def test_real_packets_are_multi_source_and_thesis_driven():
    assert len(REAL_EVIDENCE_BRIEFS) == 6
    for brief in REAL_EVIDENCE_BRIEFS:
        assert brief["id"].startswith("R")
        assert brief["source_name"]
        assert brief["source_url"].startswith("https://")
        assert 2 <= len(brief["anchor_receipts"]) <= 3
        assert brief["context_sources"]
        assert len(brief["thesis_options"]) >= 3
        assert brief["counter_case"]
        text = evidence_text(brief)
        assert "ANCHOR SOURCE:" in text
        assert "ANCHOR RECEIPTS:" in text
        assert "TENSION / CONTEXT SOURCES:" in text
        assert "PLAUSIBLE EDITORIAL THESES:" in text
        assert "STRONGEST COUNTER-CASE:" in text


def test_prompt_prioritizes_perspective_over_abstract_compression():
    brief = REAL_EVIDENCE_BRIEFS[0]
    baseline = script_prompt(brief, None)
    assert "perspective-driven investigation with receipts" in baseline
    assert "Choose ONE defensible editorial thesis" in baseline
    assert "MINIMUM evidence needed" in baseline
    assert "normally one memorable numeric receipt" in baseline
    assert "Spend more words interpreting than listing data" in baseline
    assert "Do not invent facts" in baseline
    assert "OPTIONAL TRANSFERABLE STRUCTURAL MECHANICS" not in baseline

    assisted = script_prompt(brief, [{
        "function": "contrast",
        "mechanic": "state the intuitive claim, then bound it with the decisive caveat",
        "avoid": "false certainty",
    }])
    assert "OPTIONAL TRANSFERABLE STRUCTURAL MECHANICS" in assisted
    assert "false certainty" in assisted


def test_perspective_judge_dimensions_match_editorial_goal():
    assert PERSPECTIVE_DIMENSIONS == (
        "hook_strength",
        "perspective_strength",
        "evidence_selectivity",
        "interpretive_value",
        "counter_case_quality",
        "audience_curiosity",
        "publishability",
    )
