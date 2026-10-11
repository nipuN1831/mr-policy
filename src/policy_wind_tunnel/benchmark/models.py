from dataclasses import dataclass
from enum import Enum


class Outcome(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    REFER = "REFER"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class Applicant:
    age: int
    employment: str
    monthly_income: int
    business_vintage_months: int | None
    credit_score: int | None
    existing_obligations: int
    proposed_emi: int
    loan_amount: int
    documents: frozenset[str]
    relationship_months: int
    has_delinquency: bool


@dataclass(frozen=True)
class Decision:
    outcome: Outcome
    reasons: tuple[str, ...]
