from dataclasses import asdict
from pathlib import Path
from typing import Any

from policy_wind_tunnel.adversary.mcdc import generate_mcdc
from policy_wind_tunnel.agents.critic import critique
from policy_wind_tunnel.agents.extractor import extract_contract
from policy_wind_tunnel.agents.llm import LLM
from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.mutants import MUTANTS, build_mutant
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.evaluation.harness import evaluate_contract
from policy_wind_tunnel.pipeline.regression import emit_regression_tests, verify_regression
from policy_wind_tunnel.pipeline.runner import run_suite
from policy_wind_tunnel.pipeline.triage import triage

POLICY_PATH = Path(__file__).resolve().parent.parent / "benchmark" / "lending_policy.md"
REFERENCE = wrap_engine(decide)
_MUTANT_IDS = {m.id for m in MUTANTS}


class UnknownTarget(Exception):
    pass


def demo_payload() -> dict[str, Any]:
    targets = [{"id": "reference", "clause": "", "description": "Correct implementation (should produce no findings)"}]
    targets += [{"id": m.id, "clause": m.clause, "description": m.description} for m in MUTANTS]
    return {"policy_text": POLICY_PATH.read_text(), "targets": targets}


def implementation_for(target: str):
    if target == "reference":
        return REFERENCE
    if target in _MUTANT_IDS:
        return wrap_engine(build_mutant(target))
    raise UnknownTarget(target)


def extraction_payload(policy_text: str, llm: LLM | None, use_gold: bool) -> dict[str, Any]:
    if use_gold or llm is None:
        contract, source, attempts, errors = LENDING_CONTRACT, "gold", 0, []
    else:
        result = extract_contract(policy_text, llm)
        contract, source, attempts, errors = result.contract, "llm", result.attempts, result.errors
    report = critique(policy_text, contract, llm=llm if source == "llm" else None)
    return {
        "source": source,
        "attempts": attempts,
        "repair_errors": errors,
        "contract": contract.model_dump(),
        "critique": {
            "uncited_clauses": report.uncited_clauses,
            "unreachable_rules": report.unreachable_rules,
            "uncovered_input": report.uncovered_input,
            "proposed": [a.model_dump() for a in report.proposed],
        },
    }


def _cluster_payload(cluster) -> dict[str, Any]:
    rep = cluster.representative
    return {
        "key": cluster.key,
        "clause": cluster.clause,
        "verdict": cluster.verdict,
        "severity": cluster.severity,
        "summary": cluster.summary,
        "ambiguity_id": cluster.ambiguity_id,
        "count": len(cluster.findings),
        "representative": {
            "kind": rep.kind,
            "inputs": rep.inputs,
            "expected": rep.expected,
            "actual": rep.actual,
            "fired_rules": rep.fired_rules,
            "rule_id": rep.rule_id,
            "source_quote": rep.source_quote,
            "note": rep.note,
        },
    }


def run_payload(contract: Contract, target: str) -> dict[str, Any]:
    implementation = implementation_for(target)
    cases, coverage = generate_mcdc(contract)
    findings = run_suite(contract, cases, implementation)
    report = triage(contract, findings)
    source = emit_regression_tests(report, contract.name)
    verified = verify_regression(source, buggy=implementation, fixed=REFERENCE)
    return {
        "target": target,
        "cases": len(cases),
        "case_kinds": {k: sum(1 for c in cases if c.kind == k) for k in {c.kind for c in cases}},
        "coverage": asdict(coverage),
        "findings": len(findings),
        "defects": report.defect_count,
        "needs_clarification": report.clarification_count,
        "clusters": [_cluster_payload(c) for c in report.clusters],
        "regression": {"source": source, **asdict(verified)},
    }


def benchmark_payload(contract: Contract) -> dict[str, Any]:
    return evaluate_contract(contract)
