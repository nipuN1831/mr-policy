from typing import Any

from policy_wind_tunnel.benchmark.samples import self_employed_inputs, typical_inputs


def case(inputs: dict[str, Any], outcome: str, *reasons: str) -> tuple[dict[str, Any], dict[str, Any]]:
    return inputs, {"outcome": outcome, "reasons": list(reasons)}


SMALL_LOAN = dict(existing_obligations=1000, proposed_emi=2000, loan_amount=100000)

BASELINE_CASES = [
    case(typical_inputs(), "APPROVE"),
    case(typical_inputs(age=19), "REJECT", "AGE"),
    case(typical_inputs(age=70), "REJECT", "AGE"),
    case(typical_inputs(age=21), "APPROVE"),
    case(typical_inputs(monthly_income=20000, **SMALL_LOAN), "REJECT", "INCOME"),
    case(typical_inputs(monthly_income=25000, **SMALL_LOAN), "APPROVE"),
    case(typical_inputs(existing_obligations=30000, proposed_emi=10000), "REJECT", "DTI"),
    case(typical_inputs(loan_amount=2000000), "REJECT", "CAP"),
    case(typical_inputs(documents=["id_proof", "income_proof"]), "INCOMPLETE", "DOCS"),
    case(typical_inputs(credit_score=720), "APPROVE"),
    case(typical_inputs(credit_score=670), "REFER", "SCORE_REVIEW"),
    case(typical_inputs(credit_score=600), "REJECT", "SCORE"),
    case(typical_inputs(credit_score=None), "REFER", "NO_SCORE"),
    case(self_employed_inputs(), "APPROVE"),
    case(self_employed_inputs(business_vintage_months=12), "REJECT", "INCOME"),
    case(typical_inputs(relationship_months=36, credit_score=690), "APPROVE"),
]
