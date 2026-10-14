"""Tests for the exploratory impact adapter (Phase 2 TDD)."""
import pytest

from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.simulation.exploratory import build_policy_model, run_exploratory


def test_build_policy_model_produces_one_rule_per_contract_rule():
    model = build_policy_model(LENDING_CONTRACT)
    contract_rule_ids = {r.id for _, r in LENDING_CONTRACT.all_rules()}
    model_rule_names = {r.name for r in model.rules}
    assert contract_rule_ids == model_rule_names


def test_every_input_field_is_an_outcome_metric():
    model = build_policy_model(LENDING_CONTRACT)
    field_names = {f.name for f in LENDING_CONTRACT.fields}
    assert field_names <= set(model.outcome_metrics)


def test_model_has_effects_linking_rules_to_fields():
    model = build_policy_model(LENDING_CONTRACT)
    assert len(model.effects) > 0
    causes = {e.cause for e in model.effects}
    rule_names = {r.name for r in model.rules}
    assert causes <= rule_names


def test_baseline_stats_are_non_negative():
    model = build_policy_model(LENDING_CONTRACT)
    for metric, stats in model.baseline_stats.items():
        assert stats["mean"] >= 0.0, f"{metric} has negative baseline mean"


def test_run_exploratory_returns_scenario_outcomes():
    result = run_exploratory(LENDING_CONTRACT, rule_id="R1_age", change_factor=1.5)
    assert result["changed_rule"] == "R1_age"
    assert len(result["outcomes"]) > 0
    for o in result["outcomes"]:
        assert {"field", "baseline", "simulated", "delta_pct", "ci_lower", "ci_upper", "path"} <= o.keys()


def test_run_exploratory_unknown_rule_raises():
    with pytest.raises(Exception):
        run_exploratory(LENDING_CONTRACT, rule_id="NOPE", change_factor=1.0)


def test_run_exploratory_carries_exploratory_label():
    result = run_exploratory(LENDING_CONTRACT, rule_id="R1_age", change_factor=2.0)
    assert result["label"] == "exploratory"
    assert "not a prediction" in result["note"].lower() or "model assumption" in result["note"].lower()


def test_run_exploratory_change_factor_zero_is_allowed():
    result = run_exploratory(LENDING_CONTRACT, rule_id="R1_age", change_factor=0.0)
    assert result["changed_rule"] == "R1_age"


def test_exploratory_endpoint_serves_result():
    from fastapi.testclient import TestClient
    from policy_wind_tunnel.service.app import create_app
    client = TestClient(create_app(llm=None))
    body = client.post("/api/exploratory", json={"rule_id": "R1_age", "change_factor": 1.5, "use_gold": True}).json()
    assert body["changed_rule"] == "R1_age" and body["label"] == "exploratory"


def test_exploratory_endpoint_invalid_contract_422():
    from fastapi.testclient import TestClient
    from policy_wind_tunnel.service.app import create_app
    client = TestClient(create_app(llm=None))
    assert client.post("/api/exploratory", json={"rule_id": "L1", "change_factor": 1.5, "contract": {"name": "x"}}).status_code == 422
