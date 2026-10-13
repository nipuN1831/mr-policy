import random
from dataclasses import dataclass, field
from typing import Any

from policy_wind_tunnel.adversary.mcdc import generate_mcdc
from policy_wind_tunnel.adversary.symbolic import SymbolicContract, Unsupported
from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.evaluator import evaluate
from policy_wind_tunnel.contract.expr import ExprError
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.pipeline.regression import emit_regression_tests
from policy_wind_tunnel.pipeline.runner import Implementation, run_suite
from policy_wind_tunnel.pipeline.triage import triage

DOCUMENTS = ["id_proof", "address_proof", "income_proof"]
SELF_EMPLOYED_SHARE = 0.25


class ChangeError(Exception):
    pass


def dedupe_reasons(reasons: list[str]) -> list[str]:
    return list(dict.fromkeys(reasons))


@dataclass
class SimulationResult:
    population: int
    before: dict[str, int]
    after: dict[str, int]
    flipped: int
    reason_only_changes: int
    transitions: dict[str, int]
    reasons_gained: dict[str, int]
    reasons_lost: dict[str, int]
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def flip_rate(self) -> float:
        return self.flipped / self.population if self.population else 0.0

    @property
    def changed(self) -> int:
        return self.flipped + self.reason_only_changes


def _validated_changes(changes: list[dict[str, Any]]) -> None:
    if not changes:
        raise ChangeError("no changes supplied")
    for change in changes:
        if not change.get("target") or not change.get("expr"):
            raise ChangeError("each change needs a target and an expr")


def apply_changes(contract: Contract, changes: list[dict[str, Any]]) -> Contract:
    _validated_changes(changes)
    data = contract.model_dump()
    rules = {rule["id"]: rule for stage in data["stages"] for rule in stage["rules"]}
    derived = {item["name"]: item for item in data["derived"]}
    for change in changes:
        target, source = change["target"], change["expr"]
        note = change.get("note") or f"Proposed change to {target}"
        if target in rules:
            rules[target]["when"] = source
            rules[target]["source_quote"] = note
        elif target in derived:
            derived[target]["expr"] = source
            derived[target]["source_quote"] = note
        else:
            raise ChangeError(f"no rule or derived value named {target!r}")
    try:
        return Contract.model_validate(data)
    except ValueError as error:
        raise ChangeError(str(error)) from error


def _person(rng: random.Random) -> dict[str, Any]:
    employment = "self_employed" if rng.random() < SELF_EMPLOYED_SHARE else "salaried"
    floor = 35000 if employment == "self_employed" else 25000
    income = max(8000, int(rng.lognormvariate(10.9, 0.55))) if rng.random() < 0.8 else rng.randint(floor - 6000, floor + 12000)
    obligations = int(income * rng.uniform(0, 0.4))
    emi = int(income * rng.uniform(0.05, 0.3))
    documents = list(DOCUMENTS) + (["business_proof"] if employment == "self_employed" else [])
    if rng.random() < 0.05:
        documents.remove(rng.choice(documents))
    return {
        "age": rng.randint(19, 68),
        "employment": employment,
        "monthly_income": income,
        "business_vintage_months": rng.randint(6, 120) if employment == "self_employed" else None,
        "credit_score": None if rng.random() < 0.04 else min(900, max(300, int(rng.gauss(690, 70)))),
        "existing_obligations": obligations,
        "proposed_emi": emi,
        "loan_amount": int(income * rng.uniform(2, 24)),
        "documents": documents,
        "relationship_months": rng.choice([0, 0, 6, 12, 24, 36, 60]),
        "has_delinquency": rng.random() < 0.12,
    }


def generate_population(size: int, seed: int = 20261012) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    return [_person(rng) for _ in range(size)]


def _tally(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return dict(sorted(counts.items()))


def simulate(
    before: Contract, after: Contract, population: list[dict[str, Any]], max_examples: int = 8
) -> SimulationResult:
    outcomes_before, outcomes_after = [], []
    transitions: list[str] = []
    reason_only = 0
    gained: list[str] = []
    lost: list[str] = []
    examples: list[dict[str, Any]] = []
    for person in population:
        old, new = evaluate(before, person), evaluate(after, person)
        outcomes_before.append(old["outcome"])
        outcomes_after.append(new["outcome"])
        if old == new:
            continue
        gained += [r for r in new["reasons"] if r not in old["reasons"]]
        lost += [r for r in old["reasons"] if r not in new["reasons"]]
        if old["outcome"] == new["outcome"]:
            reason_only += 1
            continue
        transitions.append(f"{old['outcome']}->{new['outcome']}")
        if len(examples) < max_examples:
            examples.append({"inputs": person, "before": old, "after": new})
    return SimulationResult(
        population=len(population),
        before=_tally(outcomes_before),
        after=_tally(outcomes_after),
        flipped=len(transitions),
        reason_only_changes=reason_only,
        transitions=_tally(transitions),
        reasons_gained=_tally(gained),
        reasons_lost=_tally(lost),
        examples=examples,
    )


def impact_on_code(changed: Contract, implementation: Implementation) -> dict[str, Any]:
    cases, _ = generate_mcdc(changed)
    findings = run_suite(changed, cases, implementation)
    report = triage(changed, findings)
    return {
        "cases": len(cases),
        "failing_cases": len(findings),
        "clauses": sorted({c.clause for c in report.clusters}),
        "clusters": [{"clause": c.clause, "summary": c.summary, "severity": c.severity} for c in report.clusters],
        "regression_tests": emit_regression_tests(report, changed.name).count("def test_"),
    }


def contract_health(contract: Contract) -> dict[str, Any]:
    try:
        symbolic = SymbolicContract(contract)
    except Unsupported:
        return {"unreachable_rules": [], "uncovered_input": None}
    return {
        "unreachable_rules": [r for r in symbolic.rule_ids() if not symbolic.can_fire(r)],
        "uncovered_input": symbolic.find_uncovered_input(),
    }


def validate_expression(contract: Contract, source: str) -> None:
    try:
        used = expr.names_in(source)
    except ExprError as error:
        raise ChangeError(str(error)) from error
    known = {f.name for f in contract.fields} | {d.name for d in contract.derived}
    if used - known:
        raise ChangeError(f"unknown names {sorted(used - known)}")
