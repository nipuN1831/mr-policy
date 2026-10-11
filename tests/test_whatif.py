import pytest

from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.contract.evaluator import coerce_inputs
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.simulation.scenarios import SCENARIOS, scenario_by_id
from policy_wind_tunnel.simulation.whatif import (
    ChangeError,
    apply_changes,
    contract_health,
    generate_population,
    impact_on_code,
    simulate,
)

REFERENCE = wrap_engine(decide)
RAISE_INCOME = [{"target": "R3a_income_salaried", "expr": 'employment != "self_employed" and monthly_income < 30000'}]


def rule(contract, rule_id):
    return next(r for _, r in contract.all_rules() if r.id == rule_id)


def test_apply_changes_replaces_a_rule_and_leaves_the_original_untouched():
    changed = apply_changes(LENDING_CONTRACT, RAISE_INCOME)
    assert "30000" in rule(changed, "R3a_income_salaried").when
    assert "25000" in rule(LENDING_CONTRACT, "R3a_income_salaried").when


def test_changed_rule_is_marked_as_a_proposed_change():
    changed = apply_changes(LENDING_CONTRACT, [{**RAISE_INCOME[0], "note": "Raise the salaried minimum to 30,000"}])
    assert rule(changed, "R3a_income_salaried").source_quote == "Raise the salaried minimum to 30,000"
    assert rule(apply_changes(LENDING_CONTRACT, RAISE_INCOME), "R3a_income_salaried").source_quote


def test_derived_values_can_be_changed():
    changed = apply_changes(LENDING_CONTRACT, [{"target": "approve_at", "expr": "700 if exception_applies else 720"}])
    assert next(d for d in changed.derived if d.name == "approve_at").expr.endswith("720")


@pytest.mark.parametrize(
    "changes",
    [
        [{"target": "NO_SUCH_RULE", "expr": "True"}],
        [{"target": "R1_age", "expr": "__import__('os')"}],
        [{"target": "R1_age", "expr": "unknown_field > 3"}],
        [{"target": "R1_age"}],
        [],
    ],
)
def test_bad_changes_are_rejected(changes):
    with pytest.raises(ChangeError):
        apply_changes(LENDING_CONTRACT, changes)


def test_population_is_seeded_valid_and_realistic():
    first = generate_population(500, seed=1)
    assert first == generate_population(500, seed=1)
    assert first != generate_population(500, seed=2)
    assert len(first) == 500
    for person in first:
        coerce_inputs(LENDING_CONTRACT, person)
    salaried = [p for p in first if p["employment"] == "salaried"]
    assert 0.5 < len(salaried) / len(first) < 0.9
    assert any(25000 <= p["monthly_income"] < 30000 for p in salaried)
    assert any(p["credit_score"] is None for p in first)


def test_no_change_means_no_flips():
    population = generate_population(800, seed=5)
    result = simulate(LENDING_CONTRACT, LENDING_CONTRACT, population)
    assert result.flipped == 0 and result.transitions == {} and result.examples == []
    assert result.before == result.after


def test_raising_the_income_floor_flips_only_applicants_in_the_gap():
    population = generate_population(4000, seed=7)
    changed = apply_changes(LENDING_CONTRACT, RAISE_INCOME)
    result = simulate(LENDING_CONTRACT, changed, population)
    assert result.flipped > 0
    assert set(result.transitions) <= {"APPROVE->REJECT", "REFER->REJECT"}
    assert result.reasons_gained["INCOME"] == result.flipped + result.reason_only_changes
    assert result.reason_only_changes > 0
    for example in result.examples:
        person = example["inputs"]
        assert person["employment"] == "salaried" and 25000 <= person["monthly_income"] < 30000
        assert "INCOME" in example["after"]["reasons"] and "INCOME" not in example["before"]["reasons"]


def test_counts_add_up_and_rate_is_a_fraction():
    population = generate_population(1000, seed=11)
    result = simulate(LENDING_CONTRACT, apply_changes(LENDING_CONTRACT, RAISE_INCOME), population)
    assert sum(result.before.values()) == sum(result.after.values()) == 1000 == result.population
    assert result.flip_rate == pytest.approx(result.flipped / 1000)
    assert sum(result.transitions.values()) == result.flipped
    assert result.changed == result.flipped + result.reason_only_changes


def test_loosening_a_rule_moves_applicants_the_other_way():
    population = generate_population(4000, seed=7)
    loosened = apply_changes(
        LENDING_CONTRACT, [{"target": "R3a_income_salaried", "expr": 'employment != "self_employed" and monthly_income < 20000'}]
    )
    result = simulate(LENDING_CONTRACT, loosened, population)
    assert result.flipped > 0
    assert all(key.startswith("REJECT->") for key in result.transitions)
    assert result.reasons_lost["INCOME"] == result.flipped + result.reason_only_changes


def test_examples_are_capped_and_ordered():
    population = generate_population(3000, seed=3)
    result = simulate(LENDING_CONTRACT, apply_changes(LENDING_CONTRACT, RAISE_INCOME), population, max_examples=4)
    assert len(result.examples) <= 4


def test_unchanged_implementation_fails_tests_for_a_changed_policy():
    changed = apply_changes(LENDING_CONTRACT, RAISE_INCOME)
    impact = impact_on_code(changed, REFERENCE)
    assert impact["failing_cases"] > 0 and impact["clauses"] == ["L3"]
    assert impact["clusters"] and impact["regression_tests"] > 0


def test_unchanged_policy_leaves_the_implementation_green():
    impact = impact_on_code(LENDING_CONTRACT, REFERENCE)
    assert impact["failing_cases"] == 0 and impact["clauses"] == []


def test_contract_health_flags_a_change_that_leaves_inputs_undecided():
    broken = apply_changes(LENDING_CONTRACT, [{"target": "R6d_reject", "expr": "credit_score < 100"}])
    health = contract_health(broken)
    assert health["uncovered_input"] is not None
    assert contract_health(LENDING_CONTRACT) == {"unreachable_rules": [], "uncovered_input": None}


def test_contract_health_flags_a_rule_that_can_never_fire():
    shadowed = apply_changes(LENDING_CONTRACT, [{"target": "R6c_review", "expr": "credit_score >= 900 and credit_score < 300"}])
    assert "R6c_review" in contract_health(shadowed)["unreachable_rules"]


def test_every_preset_scenario_applies_and_moves_someone():
    population = generate_population(3000, seed=9)
    assert len(SCENARIOS) >= 5
    for scenario in SCENARIOS:
        assert scenario.title and scenario.description and scenario.changes
        changed = apply_changes(LENDING_CONTRACT, scenario.changes)
        assert simulate(LENDING_CONTRACT, changed, population).flipped > 0, scenario.id
        assert contract_health(changed)["uncovered_input"] is None, scenario.id


def test_scenario_lookup():
    assert scenario_by_id(SCENARIOS[0].id) is SCENARIOS[0]
    with pytest.raises(KeyError):
        scenario_by_id("nope")
