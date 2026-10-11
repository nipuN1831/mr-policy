import random

import pytest

from policy_wind_tunnel.adversary.mcdc import generate_mcdc
from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.mutants import build_mutant
from policy_wind_tunnel.benchmark.samples import random_inputs, typical_inputs
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.pipeline.regression import emit_regression_tests, verify_regression
from policy_wind_tunnel.pipeline.runner import run_suite
from policy_wind_tunnel.pipeline.triage import triage

REFERENCE = wrap_engine(decide)


def suite():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    return cases


def test_correct_implementation_has_no_findings():
    assert run_suite(LENDING_CONTRACT, suite(), REFERENCE) == []


def test_seeded_bug_produces_findings_with_full_evidence():
    findings = run_suite(LENDING_CONTRACT, suite(), wrap_engine(build_mutant("M03_income_strict")))
    assert findings
    finding = findings[0]
    assert finding.expected["outcome"] != finding.actual["outcome"] or finding.expected["reasons"] != finding.actual["reasons"]
    assert finding.fired_rules
    assert finding.clause == "L3"
    assert "25,000" in finding.source_quote
    assert finding.inputs["monthly_income"] == 25000


def test_findings_are_independent_of_the_llm():
    first = run_suite(LENDING_CONTRACT, suite(), wrap_engine(build_mutant("M06_dti_strict")))
    second = run_suite(LENDING_CONTRACT, suite(), wrap_engine(build_mutant("M06_dti_strict")))
    assert [f.inputs for f in first] == [f.inputs for f in second]


def test_crashing_implementation_is_reported_as_a_crash_finding():
    def broken(inputs):
        raise ValueError("boom")

    findings = run_suite(LENDING_CONTRACT, suite()[:3], broken)
    assert len(findings) == 3
    assert all(f.kind == "crash" and "boom" in f.actual["error"] for f in findings)


def test_malformed_implementation_output_is_a_finding():
    findings = run_suite(LENDING_CONTRACT, suite()[:2], lambda inputs: {"unexpected": 1})
    assert len(findings) == 2 and all(f.kind == "mismatch" for f in findings)


def test_slow_implementation_is_cut_off():
    import time

    def slow(inputs):
        time.sleep(5)
        return {"outcome": "APPROVE", "reasons": []}

    findings = run_suite(LENDING_CONTRACT, suite()[:1], slow, timeout_seconds=0.2)
    assert findings and findings[0].kind == "timeout"


def test_triage_clusters_duplicates_and_keeps_a_minimal_example():
    findings = run_suite(LENDING_CONTRACT, suite(), wrap_engine(build_mutant("M05_dti_excludes_emi")))
    report = triage(LENDING_CONTRACT, findings)
    assert len(report.clusters) < len(findings)
    assert sum(len(c.findings) for c in report.clusters) == len(findings)
    assert all(c.representative in c.findings for c in report.clusters)
    assert all(c.verdict == "defect" for c in report.clusters)


def test_findings_on_an_unapproved_ambiguity_become_ambiguity_not_defects():
    data = LENDING_CONTRACT.model_dump()
    for item in data["ambiguities"]:
        if item["clause"] == "L4":
            item["status"] = "proposed"
    contract = Contract.model_validate(data)
    findings = run_suite(contract, suite(), wrap_engine(build_mutant("M06_dti_strict")))
    report = triage(contract, findings)
    assert report.clusters and all(c.verdict == "needs_clarification" for c in report.clusters)
    assert report.defect_count == 0


def test_severity_follows_outcome_distance():
    findings = run_suite(LENDING_CONTRACT, suite(), wrap_engine(build_mutant("M10_missing_score_rejected")))
    report = triage(LENDING_CONTRACT, findings)
    assert {c.severity for c in report.clusters} <= {"high", "medium", "low"}


def test_regression_tests_fail_on_the_bug_and_pass_on_the_fix():
    buggy = wrap_engine(build_mutant("M07_cap_off_by_one"))
    findings = run_suite(LENDING_CONTRACT, suite(), buggy)
    report = triage(LENDING_CONTRACT, findings)
    source = emit_regression_tests(report, LENDING_CONTRACT.name)
    assert "def test_" in source and "source_quote" not in source
    result = verify_regression(source, buggy=buggy, fixed=REFERENCE)
    assert result.tests > 0
    assert result.failing_on_buggy == result.tests
    assert result.passing_on_fixed == result.tests
    assert result.errors == 0


def test_regression_source_is_valid_python_for_every_mutant():
    from policy_wind_tunnel.benchmark.mutants import MUTANTS

    for mutant in MUTANTS:
        buggy = wrap_engine(build_mutant(mutant.id))
        report = triage(LENDING_CONTRACT, run_suite(LENDING_CONTRACT, suite(), buggy))
        result = verify_regression(emit_regression_tests(report, LENDING_CONTRACT.name), buggy=buggy, fixed=REFERENCE)
        assert result.tests >= 1, mutant.id
        assert result.failing_on_buggy == result.tests, mutant.id
        assert result.passing_on_fixed == result.tests, mutant.id
        assert result.errors == 0, mutant.id


def test_no_findings_means_no_regression_tests():
    report = triage(LENDING_CONTRACT, [])
    assert verify_regression(emit_regression_tests(report, "x"), buggy=REFERENCE, fixed=REFERENCE).tests == 0


def test_random_inputs_never_crash_the_runner():
    rng = random.Random(3)
    from policy_wind_tunnel.adversary.mcdc import GeneratedCase

    cases = [GeneratedCase(random_inputs(rng), "random", "", "") for _ in range(200)]
    assert run_suite(LENDING_CONTRACT, cases, REFERENCE) == []


def test_typical_input_is_unaffected():
    assert REFERENCE(typical_inputs())["outcome"] == "APPROVE"
