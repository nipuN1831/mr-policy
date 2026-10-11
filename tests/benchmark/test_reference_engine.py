import pytest
from applicants import REQUIRED_DOCS, low_income, make, self_employed

from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.models import Decision, Outcome


def test_typical_salaried_applicant_is_approved():
    assert decide(make()) == Decision(Outcome.APPROVE, ())


@pytest.mark.parametrize(
    "age,expected",
    [(20, Outcome.REJECT), (21, Outcome.APPROVE), (65, Outcome.APPROVE), (66, Outcome.REJECT)],
)
def test_age_boundaries(age, expected):
    assert decide(make(age=age)).outcome == expected


@pytest.mark.parametrize(
    "income,expected",
    [(24999, Outcome.REJECT), (25000, Outcome.APPROVE)],
)
def test_salaried_income_boundary(income, expected):
    assert decide(low_income(monthly_income=income)).outcome == expected


@pytest.mark.parametrize(
    "income,vintage,expected",
    [
        (34999, 24, Outcome.REJECT),
        (35000, 24, Outcome.APPROVE),
        (35000, 23, Outcome.REJECT),
        (35000, None, Outcome.REJECT),
    ],
)
def test_self_employed_income_and_vintage(income, vintage, expected):
    assert decide(self_employed(monthly_income=income, business_vintage_months=vintage)).outcome == expected


@pytest.mark.parametrize(
    "obligations,expected",
    [(17000, Outcome.APPROVE), (17001, Outcome.REJECT)],
)
def test_dti_boundary_at_45_percent(obligations, expected):
    result = decide(make(existing_obligations=obligations))
    assert result.outcome == expected
    if expected == Outcome.REJECT:
        assert result.reasons == ("DTI",)


def test_dti_includes_proposed_emi():
    assert decide(make(existing_obligations=5000, proposed_emi=30000)).reasons == ("DTI",)


@pytest.mark.parametrize(
    "loan,expected",
    [(1200000, Outcome.APPROVE), (1200001, Outcome.REJECT)],
)
def test_loan_cap_boundary(loan, expected):
    result = decide(make(loan_amount=loan))
    assert result.outcome == expected
    if expected == Outcome.REJECT:
        assert result.reasons == ("CAP",)


@pytest.mark.parametrize(
    "score,outcome,reasons",
    [
        (700, Outcome.APPROVE, ()),
        (699, Outcome.REFER, ("SCORE_REVIEW",)),
        (650, Outcome.REFER, ("SCORE_REVIEW",)),
        (649, Outcome.REJECT, ("SCORE",)),
        (None, Outcome.REFER, ("NO_SCORE",)),
    ],
)
def test_score_tiers(score, outcome, reasons):
    assert decide(make(credit_score=score)) == Decision(outcome, reasons)


@pytest.mark.parametrize(
    "score,expected",
    [(680, Outcome.APPROVE), (679, Outcome.REFER), (630, Outcome.REFER), (629, Outcome.REJECT)],
)
def test_existing_customer_exception_lowers_thresholds_by_20(score, expected):
    assert decide(make(relationship_months=24, credit_score=score)).outcome == expected


def test_exception_needs_24_months():
    assert decide(make(relationship_months=23, credit_score=680)).outcome == Outcome.REFER


def test_exception_denied_after_delinquency():
    assert decide(make(relationship_months=24, has_delinquency=True, credit_score=680)).outcome == Outcome.REFER


def test_missing_document_is_incomplete_and_skips_other_rules():
    result = decide(make(age=10, documents=frozenset({"address_proof", "income_proof"})))
    assert result == Decision(Outcome.INCOMPLETE, ("DOCS",))


def test_self_employed_needs_business_proof():
    assert decide(self_employed(documents=REQUIRED_DOCS)).outcome == Outcome.INCOMPLETE


def test_salaried_with_extra_document_is_fine():
    assert decide(make(documents=REQUIRED_DOCS | {"business_proof"})).outcome == Outcome.APPROVE


def test_multiple_hard_failures_are_reported_in_clause_order():
    result = decide(low_income(age=19, monthly_income=20000))
    assert result == Decision(Outcome.REJECT, ("AGE", "INCOME"))


def test_zero_income_does_not_crash():
    result = decide(make(monthly_income=0, existing_obligations=0, proposed_emi=0, loan_amount=0))
    assert result.outcome == Outcome.REJECT
    assert "INCOME" in result.reasons
