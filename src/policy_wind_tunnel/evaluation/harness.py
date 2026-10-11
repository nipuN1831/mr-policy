import random
from dataclasses import dataclass, field
from typing import Any

from policy_wind_tunnel.adversary.mcdc import generate_mcdc
from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.baseline import BASELINE_CASES
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.mutants import MUTANTS, build_mutant
from policy_wind_tunnel.benchmark.samples import random_inputs
from policy_wind_tunnel.contract.evaluator import ContractError, evaluate
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.pipeline.regression import emit_regression_tests, verify_regression
from policy_wind_tunnel.pipeline.runner import run_suite
from policy_wind_tunnel.pipeline.triage import triage

REFERENCE = wrap_engine(decide)


@dataclass
class SuiteScore:
    cases: int
    total_mutants: int
    killed: int
    false_positives_on_correct_engine: int = 0

    @property
    def recall(self) -> float:
        return self.killed / self.total_mutants if self.total_mutants else 0.0

    @property
    def precision(self) -> float:
        reported = self.killed + self.false_positives_on_correct_engine
        return self.killed / reported if reported else 1.0


@dataclass
class MutantRow:
    mutant_id: str
    clause: str
    description: str
    generated_killed: bool
    generated_cases: int
    baseline_killed: bool


@dataclass
class BenchmarkResult:
    generated: SuiteScore
    baseline: SuiteScore
    rows: list[MutantRow] = field(default_factory=list)
    regression_valid: float = 1.0


@dataclass
class Fidelity:
    samples: int
    agreement: float
    disagreements: list[dict[str, Any]]


def _baseline_kills(run) -> bool:
    return any(run(inputs) != expected for inputs, expected in BASELINE_CASES)


def run_benchmark(contract: Contract) -> BenchmarkResult:
    cases, _ = generate_mcdc(contract)
    false_positives = len(run_suite(contract, cases, REFERENCE))
    rows: list[MutantRow] = []
    valid = 0
    regression_total = 0
    for mutant in MUTANTS:
        buggy = wrap_engine(build_mutant(mutant.id))
        findings = run_suite(contract, cases, buggy)
        rows.append(
            MutantRow(
                mutant_id=mutant.id,
                clause=mutant.clause,
                description=mutant.description,
                generated_killed=bool(findings),
                generated_cases=len(findings),
                baseline_killed=_baseline_kills(buggy),
            )
        )
        if findings:
            report = triage(contract, findings)
            result = verify_regression(emit_regression_tests(report, contract.name), buggy=buggy, fixed=REFERENCE)
            regression_total += result.tests
            valid += min(result.failing_on_buggy, result.passing_on_fixed)
    generated = SuiteScore(len(cases), len(MUTANTS), sum(r.generated_killed for r in rows), false_positives)
    baseline = SuiteScore(len(BASELINE_CASES), len(MUTANTS), sum(r.baseline_killed for r in rows))
    return BenchmarkResult(generated, baseline, rows, valid / regression_total if regression_total else 1.0)


def contract_fidelity(contract: Contract, samples: int = 5000, seed: int = 20261012) -> Fidelity:
    rng = random.Random(seed)
    disagreements: list[dict[str, Any]] = []
    for _ in range(samples):
        inputs = random_inputs(rng)
        expected = REFERENCE(inputs)
        try:
            actual = evaluate(contract, inputs)
        except ContractError as error:
            actual = {"error": str(error)}
        if actual != expected and len(disagreements) < 5:
            disagreements.append({"inputs": inputs, "contract": actual, "engine": expected})
        elif actual != expected:
            disagreements.append({})
    bad = len(disagreements)
    return Fidelity(samples, (samples - bad) / samples, [d for d in disagreements if d][:5])


def evaluate_contract(contract: Contract) -> dict[str, Any]:
    benchmark = run_benchmark(contract)
    fidelity = contract_fidelity(contract, samples=3000)
    return {
        "fidelity": fidelity.agreement,
        "recall": benchmark.generated.recall,
        "precision": benchmark.generated.precision,
        "false_positives": benchmark.generated.false_positives_on_correct_engine,
        "baseline_recall": benchmark.baseline.recall,
        "cases": benchmark.generated.cases,
        "baseline_cases": benchmark.baseline.cases,
        "regression_valid": benchmark.regression_valid,
        "rows": [row.__dict__ for row in benchmark.rows],
    }
