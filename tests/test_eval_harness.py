import pytest

import agent
import eval_harness


@pytest.fixture(autouse=True)
def isolate_trace_path(tmp_path, monkeypatch):
    """Point agent.py's ReasoningTrace writer at a throwaway file so running
    eval_harness's scenarios through agent.recommend during tests never
    appends to the real ai_interactions.md (same pattern as
    tests/test_agent.py)."""
    path = tmp_path / "ai_interactions.md"
    monkeypatch.setattr(agent, "TRACE_PATH", str(path))
    return path


def test_all_scenarios_declare_a_valid_expected_outcome():
    scenarios = eval_harness.build_scenarios()

    assert len(scenarios) >= 5
    assert all(s.expected in ("pass", "fail") for s in scenarios)
    # The ticket requires at least one scenario designed to fail.
    assert any(s.expected == "fail" for s in scenarios)
    # And the harness should also cover ordinary passing cases.
    assert any(s.expected == "pass" for s in scenarios)


def test_designed_to_fail_scenario_actually_fails_against_agent_recommend():
    scenarios = {s.name: s for s in eval_harness.build_scenarios()}
    scenario = scenarios["impossible_artist_repeat"]
    assert scenario.expected == "fail"

    result = eval_harness.run_scenario(scenario)

    assert result.actual == "fail"
    assert result.matches_expected is True
    assert result.final_score < agent.SCORE_THRESHOLD


def test_cold_start_scenario_actually_passes_against_agent_recommend():
    scenarios = {s.name: s for s in eval_harness.build_scenarios()}
    scenario = scenarios["cold_start"]
    assert scenario.expected == "pass"

    result = eval_harness.run_scenario(scenario)

    assert result.actual == "pass"
    assert result.matches_expected is True
    assert result.final_score >= agent.SCORE_THRESHOLD


def test_run_all_matches_every_scenario_as_designed():
    """End-to-end self-check: every scenario in the fixed set should behave
    exactly as its `expected` field declares. This is cheap insurance that
    the harness's scenarios keep working as agent.py evolves -- if a future
    change to agent.py breaks this, it's a signal worth investigating, not
    just a harness quirk."""
    results = eval_harness.run_all()

    mismatches = [r for r in results if not r.matches_expected]
    assert mismatches == [], f"scenarios misbehaved: {mismatches}"
