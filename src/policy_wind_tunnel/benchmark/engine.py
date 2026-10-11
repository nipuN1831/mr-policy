from collections.abc import Callable
from dataclasses import dataclass

from policy_wind_tunnel.benchmark.models import Applicant, Decision, Outcome

MIN_AGE = 21
MAX_AGE = 65
SALARIED_MIN_INCOME = 25000
SELF_EMPLOYED_MIN_INCOME = 35000
SELF_EMPLOYED_MIN_VINTAGE_MONTHS = 24
MAX_DTI_PERCENT = 45
MAX_LOAN_INCOME_MULTIPLE = 20
APPROVE_SCORE = 700
REVIEW_SCORE = 650
EXCEPTION_RELATIONSHIP_MONTHS = 24
EXCEPTION_SCORE_REDUCTION = 20
BASE_DOCUMENTS = frozenset({"id_proof", "address_proof", "income_proof"})


def required_documents(applicant: Applicant) -> frozenset[str]:
    if applicant.employment == "self_employed":
        return BASE_DOCUMENTS | {"business_proof"}
    return BASE_DOCUMENTS


def age_ok(applicant: Applicant) -> bool:
    return MIN_AGE <= applicant.age <= MAX_AGE


def income_ok(applicant: Applicant) -> bool:
    if applicant.employment == "self_employed":
        vintage = applicant.business_vintage_months
        return (
            applicant.monthly_income >= SELF_EMPLOYED_MIN_INCOME
            and vintage is not None
            and vintage >= SELF_EMPLOYED_MIN_VINTAGE_MONTHS
        )
    return applicant.monthly_income >= SALARIED_MIN_INCOME


def dti_ok(applicant: Applicant) -> bool:
    if applicant.monthly_income <= 0:
        return False
    obligations = applicant.existing_obligations + applicant.proposed_emi
    return obligations * 100 <= MAX_DTI_PERCENT * applicant.monthly_income


def cap_ok(applicant: Applicant) -> bool:
    return applicant.loan_amount <= MAX_LOAN_INCOME_MULTIPLE * applicant.monthly_income


def score_thresholds(applicant: Applicant) -> tuple[int, int]:
    eligible = applicant.relationship_months >= EXCEPTION_RELATIONSHIP_MONTHS and not applicant.has_delinquency
    reduction = EXCEPTION_SCORE_REDUCTION if eligible else 0
    return APPROVE_SCORE - reduction, REVIEW_SCORE - reduction


def score_decision(applicant: Applicant, thresholds: Callable[[Applicant], tuple[int, int]]) -> Decision:
    if applicant.credit_score is None:
        return Decision(Outcome.REFER, ("NO_SCORE",))
    approve_at, review_at = thresholds(applicant)
    if applicant.credit_score >= approve_at:
        return Decision(Outcome.APPROVE, ())
    if applicant.credit_score >= review_at:
        return Decision(Outcome.REFER, ("SCORE_REVIEW",))
    return Decision(Outcome.REJECT, ("SCORE",))


@dataclass(frozen=True)
class Rules:
    age_ok: Callable[[Applicant], bool] = age_ok
    income_ok: Callable[[Applicant], bool] = income_ok
    dti_ok: Callable[[Applicant], bool] = dti_ok
    cap_ok: Callable[[Applicant], bool] = cap_ok
    score_thresholds: Callable[[Applicant], tuple[int, int]] = score_thresholds
    score_decision: Callable[[Applicant, Callable[[Applicant], tuple[int, int]]], Decision] = score_decision


DEFAULT_RULES = Rules()


def decide(applicant: Applicant, rules: Rules = DEFAULT_RULES) -> Decision:
    if not required_documents(applicant) <= applicant.documents:
        return Decision(Outcome.INCOMPLETE, ("DOCS",))
    checks = (
        ("AGE", rules.age_ok(applicant)),
        ("INCOME", rules.income_ok(applicant)),
        ("DTI", rules.dti_ok(applicant)),
        ("CAP", rules.cap_ok(applicant)),
    )
    failures = tuple(reason for reason, passed in checks if not passed)
    if failures:
        return Decision(Outcome.REJECT, failures)
    return rules.score_decision(applicant, rules.score_thresholds)
