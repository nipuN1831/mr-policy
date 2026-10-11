import random
from typing import Any

TYPICAL: dict[str, Any] = {
    "age": 35,
    "employment": "salaried",
    "monthly_income": 60000,
    "business_vintage_months": None,
    "credit_score": 750,
    "existing_obligations": 5000,
    "proposed_emi": 10000,
    "loan_amount": 600000,
    "documents": ["id_proof", "address_proof", "income_proof"],
    "relationship_months": 0,
    "has_delinquency": False,
}

ALL_DOCUMENTS = ["id_proof", "address_proof", "income_proof", "business_proof"]


def typical_inputs(**overrides: Any) -> dict[str, Any]:
    data = {**TYPICAL, "documents": list(TYPICAL["documents"])}
    data.update(overrides)
    return data


def self_employed_inputs(**overrides: Any) -> dict[str, Any]:
    base = {
        "employment": "self_employed",
        "monthly_income": 40000,
        "business_vintage_months": 36,
        "existing_obligations": 2000,
        "proposed_emi": 4000,
        "loan_amount": 300000,
        "documents": list(ALL_DOCUMENTS),
    }
    base.update(overrides)
    return typical_inputs(**base)


def random_inputs(rng: random.Random) -> dict[str, Any]:
    employment = rng.choice(["salaried", "self_employed"])
    income = rng.choice([24999, 25000, 34999, 35000, rng.randint(0, 200000), rng.randint(20000, 120000)])
    dti_total = (45 * income) // 100 + rng.choice([-1, 0, 0, 1, rng.randint(-5000, 5000)])
    dti_total = max(dti_total, 0)
    existing = rng.randint(0, dti_total)
    documents = list(ALL_DOCUMENTS if employment == "self_employed" else ALL_DOCUMENTS[:3])
    if rng.random() < 0.2:
        documents.remove(rng.choice(documents))
    return {
        "age": rng.choice([20, 21, 35, 65, 66, rng.randint(18, 80)]),
        "employment": employment,
        "monthly_income": income,
        "business_vintage_months": rng.choice([None, 23, 24, rng.randint(0, 120)]),
        "credit_score": rng.choice([None, 629, 630, 649, 650, 679, 680, 699, 700, rng.randint(300, 900)]),
        "existing_obligations": existing,
        "proposed_emi": dti_total - existing,
        "loan_amount": rng.choice([20 * income, 20 * income + 1, 20 * income - 1, rng.randint(0, 6_000_000)]),
        "documents": documents,
        "relationship_months": rng.choice([0, 23, 24, 25, rng.randint(0, 120)]),
        "has_delinquency": rng.random() < 0.3,
    }
