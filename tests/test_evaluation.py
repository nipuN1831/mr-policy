from policy_wind_tunnel.benchmark.baseline import BASELINE_CASES
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.evaluation.harness import (
    contract_fidelity,
    evaluate_contract,
    run_benchmark,
)


def test_gold_contract_scores_perfectly():
    result = run_benchmark(LENDING_CONTRACT)
    assert result.generated.recall == 1.0
    assert result.generated.precision == 1.0
    assert result.generated.false_positives_on_correct_engine == 0
    assert result.regression_valid == 1.0


def test_baseline_is_measured_on_the_same_mutants():
    result = run_benchmark(LENDING_CONTRACT)
    assert result.baseline.total_mutants == 10
    assert result.baseline.killed == 4
    assert result.baseline.cases == len(BASELINE_CASES)
    assert result.generated.killed > result.baseline.killed


def test_per_mutant_rows_are_reported():
    result = run_benchmark(LENDING_CONTRACT)
    assert len(result.rows) == 10
    row = result.rows[0]
    assert row.mutant_id and row.clause and isinstance(row.generated_killed, bool)
    assert isinstance(row.baseline_killed, bool)


def test_a_wrong_contract_lowers_precision():
    data = LENDING_CONTRACT.model_dump()
    for stage in data["stages"]:
        for rule in stage["rules"]:
            if rule["id"] == "R5_cap":
                rule["when"] = "loan_amount > 10 * monthly_income"
    wrong = Contract.model_validate(data)
    result = run_benchmark(wrong)
    assert result.generated.precision < 1.0
    assert result.generated.false_positives_on_correct_engine > 0


def test_contract_fidelity_is_one_for_gold_and_lower_for_a_wrong_contract():
    assert contract_fidelity(LENDING_CONTRACT, samples=2000).agreement == 1.0
    data = LENDING_CONTRACT.model_dump()
    for stage in data["stages"]:
        for rule in stage["rules"]:
            if rule["id"] == "R1_age":
                rule["when"] = "not (21 <= age <= 64)"
    assert contract_fidelity(Contract.model_validate(data), samples=2000).agreement < 1.0


def test_evaluate_contract_returns_a_serialisable_summary():
    summary = evaluate_contract(LENDING_CONTRACT)
    assert {"fidelity", "recall", "precision", "baseline_recall", "cases", "baseline_cases"} <= summary.keys()
    assert summary["recall"] == 1.0
