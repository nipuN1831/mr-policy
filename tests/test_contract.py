from pathlib import Path

import pytest
from pydantic import ValidationError

from policy_wind_tunnel.contract.evaluator import ContractError, coerce_inputs, evaluate, evaluate_traced
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.benchmark.samples import typical_inputs

POLICY_TEXT = (
    Path(__file__).parent.parent / "src/policy_wind_tunnel/benchmark/lending_policy.md"
).read_text()


def minimal(**overrides):
    base = dict(
        name="t",
        outcomes=["YES", "NO"],
        fields=[{"name": "x", "kind": "int"}],
        stages=[
            {
                "name": "s",
                "mode": "first_match",
                "rules": [
                    {"id": "R1", "clause": "C1", "source_quote": "q", "when": "x >= 1", "outcome": "YES"},
                    {"id": "R2", "clause": "C1", "source_quote": "q", "when": "True", "outcome": "NO", "reason": "X"},
                ],
            }
        ],
    )
    base.update(overrides)
    return base


def test_minimal_contract_is_valid_and_evaluates():
    contract = Contract.model_validate(minimal())
    assert evaluate(contract, {"x": 1}) == {"outcome": "YES", "reasons": []}
    assert evaluate(contract, {"x": 0}) == {"outcome": "NO", "reasons": ["X"]}


def test_expression_with_unknown_field_is_rejected():
    stages = minimal()["stages"]
    stages[0]["rules"][0]["when"] = "y >= 1"
    with pytest.raises(ValidationError):
        Contract.model_validate(minimal(stages=stages))


def test_duplicate_rule_ids_are_rejected():
    stages = minimal()["stages"]
    stages[0]["rules"][1]["id"] = "R1"
    with pytest.raises(ValidationError):
        Contract.model_validate(minimal(stages=stages))


def test_undeclared_outcome_is_rejected():
    stages = minimal()["stages"]
    stages[0]["rules"][0]["outcome"] = "MAYBE"
    with pytest.raises(ValidationError):
        Contract.model_validate(minimal(stages=stages))


def test_unsafe_expression_is_rejected_by_the_schema():
    stages = minimal()["stages"]
    stages[0]["rules"][0]["when"] = "__import__('os')"
    with pytest.raises(ValidationError):
        Contract.model_validate(minimal(stages=stages))


def test_derived_values_can_only_use_earlier_names():
    derived = [{"name": "d1", "expr": "d2 + 1", "clause": "C"}, {"name": "d2", "expr": "x", "clause": "C"}]
    with pytest.raises(ValidationError):
        Contract.model_validate(minimal(derived=derived))


def test_contract_with_no_deciding_rule_raises_at_evaluation():
    stages = minimal()["stages"]
    stages[0]["rules"] = stages[0]["rules"][:1]
    contract = Contract.model_validate(minimal(stages=stages))
    with pytest.raises(ContractError):
        evaluate(contract, {"x": 0})


def test_collect_stage_reports_every_firing_rule_in_order():
    contract = Contract.model_validate(
        minimal(
            stages=[
                {
                    "name": "checks",
                    "mode": "collect",
                    "rules": [
                        {"id": "A", "clause": "C", "source_quote": "q", "when": "x < 5", "outcome": "NO", "reason": "LOW"},
                        {"id": "B", "clause": "C", "source_quote": "q", "when": "x < 3", "outcome": "NO", "reason": "VERY_LOW"},
                    ],
                },
                {
                    "name": "final",
                    "mode": "first_match",
                    "rules": [{"id": "Z", "clause": "C", "source_quote": "q", "when": "True", "outcome": "YES"}],
                },
            ]
        )
    )
    assert evaluate(contract, {"x": 1}) == {"outcome": "NO", "reasons": ["LOW", "VERY_LOW"]}
    assert evaluate(contract, {"x": 4}) == {"outcome": "NO", "reasons": ["LOW"]}
    assert evaluate(contract, {"x": 9}) == {"outcome": "YES", "reasons": []}


def test_traced_evaluation_names_the_rules_that_fired():
    result, fired = evaluate_traced(LENDING_CONTRACT, typical_inputs(age=19))
    assert result == {"outcome": "REJECT", "reasons": ["AGE"]}
    assert fired == ["R1_age"]


def test_inputs_are_validated():
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, {**typical_inputs(), "unknown": 1})
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, typical_inputs(employment="freelance"))
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, typical_inputs(age=None))
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, typical_inputs(age=True))
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, typical_inputs(documents=["passport"]))
    missing = typical_inputs()
    del missing["age"]
    with pytest.raises(ContractError):
        coerce_inputs(LENDING_CONTRACT, missing)


def test_nullable_fields_default_to_none_when_absent():
    inputs = typical_inputs()
    del inputs["credit_score"]
    assert coerce_inputs(LENDING_CONTRACT, inputs)["credit_score"] is None


def test_every_gold_source_quote_appears_verbatim_in_the_policy():
    for stage in LENDING_CONTRACT.stages:
        for rule in stage.rules:
            if rule.source_quote:
                assert rule.source_quote in POLICY_TEXT, rule.id


def test_every_gold_rule_cites_a_known_clause():
    clauses = {f"L{i}" for i in range(1, 8)}
    for stage in LENDING_CONTRACT.stages:
        for rule in stage.rules:
            assert rule.clause in clauses, rule.id


def test_gold_contract_round_trips_through_json():
    assert Contract.model_validate_json(LENDING_CONTRACT.model_dump_json()) == LENDING_CONTRACT


def test_gold_contract_lists_approved_ambiguities():
    assert len(LENDING_CONTRACT.ambiguities) >= 3
    assert all(a.status == "approved" for a in LENDING_CONTRACT.ambiguities)
