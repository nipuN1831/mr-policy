from collections.abc import Callable
from dataclasses import dataclass, replace

from policy_wind_tunnel.benchmark import engine
from policy_wind_tunnel.benchmark.models import Applicant, Decision, Outcome


@dataclass(frozen=True)
class Mutant:
    id: str
    clause: str
    description: str


MUTANTS = [
    Mutant("M01_age_lower_exclusive", "L1", "Minimum age check uses > instead of >=, so age 21 is rejected"),
    Mutant("M02_age_upper_exclusive", "L1", "Maximum age check uses < instead of <=, so age 65 is rejected"),
    Mutant("M03_income_strict", "L3", "Salaried minimum income uses > instead of >=, so exactly 25,000 is rejected"),
    Mutant("M04_selfemp_vintage_ignored", "L3", "Self-employed business-age requirement is never checked"),
    Mutant("M05_dti_excludes_emi", "L4", "Debt-to-income ignores the proposed EMI"),
    Mutant("M06_dti_strict", "L4", "DTI check uses < instead of <=, so exactly 45% is rejected"),
    Mutant("M07_cap_off_by_one", "L5", "Loan cap check uses < instead of <=, so exactly 20x income is rejected"),
    Mutant("M08_score_review_boundary", "L6", "Score of exactly 650 is rejected instead of referred"),
    Mutant("M09_exception_ignores_delinquency", "L7", "Existing-customer exception ignores delinquency"),
    Mutant("M10_missing_score_rejected", "L6", "A missing credit score is rejected instead of referred"),
]


def _age_lower_exclusive(a: Applicant) -> bool:
    return engine.MIN_AGE < a.age <= engine.MAX_AGE


def _age_upper_exclusive(a: Applicant) -> bool:
    return engine.MIN_AGE <= a.age < engine.MAX_AGE


def _income_strict(a: Applicant) -> bool:
    if a.employment == "self_employed":
        return engine.income_ok(a)
    return a.monthly_income > engine.SALARIED_MIN_INCOME


def _vintage_ignored(a: Applicant) -> bool:
    minimum = engine.SELF_EMPLOYED_MIN_INCOME if a.employment == "self_employed" else engine.SALARIED_MIN_INCOME
    return a.monthly_income >= minimum


def _dti_excludes_emi(a: Applicant) -> bool:
    if a.monthly_income <= 0:
        return False
    return a.existing_obligations * 100 <= engine.MAX_DTI_PERCENT * a.monthly_income


def _dti_strict(a: Applicant) -> bool:
    if a.monthly_income <= 0:
        return False
    return (a.existing_obligations + a.proposed_emi) * 100 < engine.MAX_DTI_PERCENT * a.monthly_income


def _cap_off_by_one(a: Applicant) -> bool:
    return a.loan_amount < engine.MAX_LOAN_INCOME_MULTIPLE * a.monthly_income


def _review_boundary_rejects(
    a: Applicant, thresholds: Callable[[Applicant], tuple[int, int]]
) -> Decision:
    if a.credit_score is not None and a.credit_score == thresholds(a)[1]:
        return Decision(Outcome.REJECT, ("SCORE",))
    return engine.score_decision(a, thresholds)


def _exception_ignores_delinquency(a: Applicant) -> tuple[int, int]:
    eligible = a.relationship_months >= engine.EXCEPTION_RELATIONSHIP_MONTHS
    reduction = engine.EXCEPTION_SCORE_REDUCTION if eligible else 0
    return engine.APPROVE_SCORE - reduction, engine.REVIEW_SCORE - reduction


def _missing_score_rejected(
    a: Applicant, thresholds: Callable[[Applicant], tuple[int, int]]
) -> Decision:
    if a.credit_score is None:
        return Decision(Outcome.REJECT, ("NO_SCORE",))
    return engine.score_decision(a, thresholds)


_RULES: dict[str, engine.Rules] = {
    "M01_age_lower_exclusive": replace(engine.DEFAULT_RULES, age_ok=_age_lower_exclusive),
    "M02_age_upper_exclusive": replace(engine.DEFAULT_RULES, age_ok=_age_upper_exclusive),
    "M03_income_strict": replace(engine.DEFAULT_RULES, income_ok=_income_strict),
    "M04_selfemp_vintage_ignored": replace(engine.DEFAULT_RULES, income_ok=_vintage_ignored),
    "M05_dti_excludes_emi": replace(engine.DEFAULT_RULES, dti_ok=_dti_excludes_emi),
    "M06_dti_strict": replace(engine.DEFAULT_RULES, dti_ok=_dti_strict),
    "M07_cap_off_by_one": replace(engine.DEFAULT_RULES, cap_ok=_cap_off_by_one),
    "M08_score_review_boundary": replace(engine.DEFAULT_RULES, score_decision=_review_boundary_rejects),
    "M09_exception_ignores_delinquency": replace(
        engine.DEFAULT_RULES, score_thresholds=_exception_ignores_delinquency
    ),
    "M10_missing_score_rejected": replace(engine.DEFAULT_RULES, score_decision=_missing_score_rejected),
}


def build_mutant(mutant_id: str) -> Callable[[Applicant], Decision]:
    rules = _RULES[mutant_id]
    return lambda applicant: engine.decide(applicant, rules)
