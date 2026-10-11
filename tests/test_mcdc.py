from policy_wind_tunnel.adversary.mcdc import generate_mcdc
from policy_wind_tunnel.contract.evaluator import coerce_inputs, evaluate
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT


def values(cases, field, where=lambda inputs: True):
    return {c.inputs[field] for c in cases if where(c.inputs)}


def test_cases_are_valid_and_evaluable():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    assert cases
    for case in cases:
        coerce_inputs(LENDING_CONTRACT, case.inputs)
        evaluate(LENDING_CONTRACT, case.inputs)


def test_generation_is_deterministic():
    first, _ = generate_mcdc(LENDING_CONTRACT)
    second, _ = generate_mcdc(LENDING_CONTRACT)
    assert [c.inputs for c in first] == [c.inputs for c in second]


def test_case_count_is_reasonable():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    assert 40 <= len(cases) <= 900


def test_no_duplicate_inputs():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    keys = [repr(sorted(c.inputs.items(), key=lambda kv: kv[0])) for c in cases]
    assert len(keys) == len(set(keys))


def test_every_rule_is_covered_in_both_directions():
    _, report = generate_mcdc(LENDING_CONTRACT)
    assert report.uncovered_rules == []
    assert report.unreachable_rules == []


def test_age_boundaries_on_both_edges():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    assert {20, 21, 65, 66} <= values(cases, "age")


def test_salaried_income_boundary():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    salaried = lambda i: i["employment"] == "salaried"
    assert {24999, 25000} <= values(cases, "monthly_income", salaried)


def test_self_employed_vintage_and_income_boundaries():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    self_employed = lambda i: i["employment"] == "self_employed"
    assert {23, 24} <= values(cases, "business_vintage_months", self_employed)
    assert {34999, 35000} <= values(cases, "monthly_income", self_employed)
    assert None in values(cases, "business_vintage_months", self_employed)


def test_dti_exact_boundary_exists_on_both_sides():
    cases, _ = generate_mcdc(LENDING_CONTRACT)

    def total(i):
        return i["existing_obligations"] + i["proposed_emi"]

    at_limit = [c for c in cases if c.inputs["monthly_income"] > 0 and total(c.inputs) * 100 == 45 * c.inputs["monthly_income"]]
    just_over = [
        c
        for c in cases
        if c.inputs["monthly_income"] > 0
        and total(c.inputs) * 100 > 45 * c.inputs["monthly_income"]
        and (total(c.inputs) - 1) * 100 <= 45 * c.inputs["monthly_income"]
    ]
    assert at_limit and just_over


def test_loan_cap_exact_boundary_exists_on_both_sides():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    at_cap = [c for c in cases if c.inputs["loan_amount"] == 20 * c.inputs["monthly_income"] and c.inputs["monthly_income"] > 0]
    over = [c for c in cases if c.inputs["loan_amount"] == 20 * c.inputs["monthly_income"] + 1]
    assert at_cap and over


def test_score_boundaries_for_standard_and_exception_customers():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    standard = lambda i: i["relationship_months"] < 24 or i["has_delinquency"]
    exception = lambda i: i["relationship_months"] >= 24 and not i["has_delinquency"]
    assert {649, 650, 699, 700} <= values(cases, "credit_score", standard)
    assert {629, 630, 679, 680} <= values(cases, "credit_score", exception)
    assert None in values(cases, "credit_score")


def test_exception_tenure_and_delinquency_boundaries():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    assert {23, 24} <= values(cases, "relationship_months")
    assert {True, False} <= values(cases, "has_delinquency", lambda i: i["relationship_months"] >= 24)


def test_each_document_is_toggled():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    seen = {frozenset(c.inputs["documents"]) for c in cases}
    for missing in ("id_proof", "address_proof", "income_proof"):
        assert any(missing not in docs for docs in seen), missing
    assert any("business_proof" not in docs for docs in seen)


def test_cases_name_the_rule_and_field_they_target():
    cases, _ = generate_mcdc(LENDING_CONTRACT)
    paired = [c for c in cases if c.kind == "mcdc"]
    assert paired and all(c.rule_id and c.field for c in paired)
    assert {c.rule_id for c in paired} >= {"R1_age", "R4_dti", "R5_cap", "R6c_review"}
    assert all(c.rule_id for c in cases if c.kind == "witness")
