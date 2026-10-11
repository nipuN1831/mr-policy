from collections.abc import Callable
from typing import Any

from policy_wind_tunnel.benchmark.models import Applicant, Decision


def applicant_from_dict(data: dict[str, Any]) -> Applicant:
    return Applicant(
        age=data["age"],
        employment=data["employment"],
        monthly_income=data["monthly_income"],
        business_vintage_months=data.get("business_vintage_months"),
        credit_score=data.get("credit_score"),
        existing_obligations=data["existing_obligations"],
        proposed_emi=data["proposed_emi"],
        loan_amount=data["loan_amount"],
        documents=frozenset(data["documents"]),
        relationship_months=data["relationship_months"],
        has_delinquency=data["has_delinquency"],
    )


def decision_to_dict(decision: Decision) -> dict[str, Any]:
    return {"outcome": decision.outcome.value, "reasons": list(decision.reasons)}


def wrap_engine(decide: Callable[[Applicant], Decision]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    def decide_json(data: dict[str, Any]) -> dict[str, Any]:
        return decision_to_dict(decide(applicant_from_dict(data)))

    return decide_json
