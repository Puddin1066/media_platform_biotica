from real_rhetoric_benchmark import REAL_EVIDENCE_BRIEFS, evidence_text, script_prompt


def test_real_packets_are_specific_and_source_anchored():
    assert len(REAL_EVIDENCE_BRIEFS) == 6
    for brief in REAL_EVIDENCE_BRIEFS:
        assert brief["id"].startswith("R")
        assert brief["source_name"]
        assert brief["source_url"].startswith("https://")
        assert len(brief["receipts"]) >= 4
        assert brief["tension"]
        assert brief["counter_case"]
        text = evidence_text(brief)
        assert "SOURCE:" in text
        assert "RECEIPTS:" in text
        assert "TENSION:" in text
        assert "STRONGEST COUNTER-CASE:" in text


def test_prompt_requires_receipts_and_does_not_require_retrieval():
    brief = REAL_EVIDENCE_BRIEFS[0]
    baseline = script_prompt(brief, None)
    assert "Name the publication, regulator, trial, institution, or technology" in baseline
    assert "at least two concrete numbers" in baseline
    assert "apparently conspiratorial/weird element" in baseline
    assert "Do not invent any fact beyond this packet" in baseline
    assert "OPTIONAL TRANSFERABLE STRUCTURAL MECHANICS" not in baseline

    assisted = script_prompt(brief, [{
        "function": "contrast",
        "mechanic": "state the intuitive claim, then bound it with the decisive caveat",
        "avoid": "false certainty",
    }])
    assert "OPTIONAL TRANSFERABLE STRUCTURAL MECHANICS" in assisted
    assert "false certainty" in assisted
