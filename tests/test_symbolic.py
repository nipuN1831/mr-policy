import random

import pytest

from policy_wind_tunnel.adversary.symbolic import SymbolicContract, Unsupported
from policy_wind_tunnel.benchmark.samples import random_inputs, typical_inputs
from policy_wind_tunnel.contract.evaluator import evaluate_traced
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract


def contract_with(fields, rules, derived=None, mode="first_match"):
    return Contract.model_validate(
        dict(
            name="t",
            outcomes=["YES", "NO"],
            fields=fields,
            derived=derived or [],
            stages=[{"name": "s", "mode": mode, "rules": rules}],
        )
    )


def rule(rule_id, when, outcome="NO", reason=None):
    return {"id": rule_id, "clause": "C", "when": when, "outcome": outcome, "reason": reason}


def test_symbolic_firing_matches_the_concrete_evaluator_on_random_inputs():
    symbolic = SymbolicContract(LENDING_CONTRACT)
    rng = random.Random(77)
    for _ in range(1500):
        inputs = random_inputs(rng)
        _, fired = evaluate_traced(LENDING_CONTRACT, inputs)
        assert symbolic.fired_rules(inputs) == set(fired), inputs


def test_symbolic_firing_handles_none_scores_and_missing_documents():
    symbolic = SymbolicContract(LENDING_CONTRACT)
    for inputs in (
        typical_inputs(credit_score=None),
        typical_inputs(documents=["id_proof"]),
        typical_inputs(employment="self_employed", business_vintage_months=None),
    ):
        _, fired = evaluate_traced(LENDING_CONTRACT, inputs)
        assert symbolic.fired_rules(inputs) == set(fired)


def test_unreachable_rule_is_reported_as_unsatisfiable():
    contract = contract_with(
        [{"name": "x", "kind": "int", "min": 0, "max": 10}],
        [rule("A", "x >= 0", "YES"), rule("B", "x > 5", "NO"), rule("C", "True", "NO")],
    )
    symbolic = SymbolicContract(contract)
    assert symbolic.can_fire("A")
    assert not symbolic.can_fire("B")


def test_incomplete_contract_gets_a_counterexample_input():
    contract = contract_with(
        [{"name": "x", "kind": "int", "min": 0, "max": 10}],
        [rule("A", "x >= 5", "YES")],
    )
    gap = SymbolicContract(contract).find_uncovered_input()
    assert gap is not None and gap["x"] < 5


def test_complete_contract_has_no_uncovered_input():
    assert SymbolicContract(LENDING_CONTRACT).find_uncovered_input() is None


def test_find_model_respects_field_domains():
    contract = contract_with(
        [{"name": "x", "kind": "int", "min": 3, "max": 4}],
        [rule("A", "x >= 4", "YES"), rule("B", "True", "NO")],
    )
    model = SymbolicContract(contract).solve_rule("A")
    assert model == {"x": 4}


def test_string_kind_fields_are_not_supported_symbolically():
    contract = contract_with([{"name": "s", "kind": "str"}], [rule("A", "s == 'a'", "YES"), rule("B", "True")])
    with pytest.raises(Unsupported):
        SymbolicContract(contract)
