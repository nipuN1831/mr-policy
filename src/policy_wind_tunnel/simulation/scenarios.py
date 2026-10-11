from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    description: str
    changes: list[dict[str, Any]]


SCENARIOS = [
    Scenario(
        "raise_salaried_income",
        "Raise the salaried income floor to 30,000",
        "Clause L3: salaried applicants now need verified monthly income of at least 30,000.",
        [
            {
                "target": "R3a_income_salaried",
                "expr": 'employment != "self_employed" and monthly_income < 30000',
                "note": "Salaried verified monthly income must be at least 30,000.",
            }
        ],
    ),
    Scenario(
        "tighten_dti",
        "Tighten debt-to-income to 40%",
        "Clause L4: total obligations may not exceed 40% of income instead of 45%.",
        [
            {
                "target": "R4_dti",
                "expr": "monthly_income <= 0 or obligations * 100 > 40 * monthly_income",
                "note": "Obligations divided by income must not exceed 40%.",
            }
        ],
    ),
    Scenario(
        "lower_loan_cap",
        "Lower the loan cap to 12x income",
        "Clause L5: the loan amount may not exceed 12 times monthly income instead of 20 times.",
        [
            {
                "target": "R5_cap",
                "expr": "loan_amount > 12 * monthly_income",
                "note": "The loan amount must not exceed 12 times verified monthly income.",
            }
        ],
    ),
    Scenario(
        "raise_score_bar",
        "Raise the approval score to 720",
        "Clause L6: automatic approval needs a score of 720 (exception customers 700); the review band moves with it.",
        [
            {
                "target": "approve_at",
                "expr": "700 if exception_applies else 720",
                "note": "Score at least 720 is approved.",
            },
            {
                "target": "review_at",
                "expr": "650 if exception_applies else 670",
                "note": "Score from 670 is referred.",
            },
        ],
    ),
    Scenario(
        "shorter_loyalty",
        "Loyalty exception after 12 months",
        "Clause L7: existing customers qualify for the lower score thresholds after 12 months instead of 24.",
        [
            {
                "target": "exception_applies",
                "expr": "relationship_months >= 12 and not has_delinquency",
                "note": "A relationship of at least 12 months and no delinquency.",
            }
        ],
    ),
    Scenario(
        "raise_age_limit",
        "Raise the maximum age to 70",
        "Clause L1: applicants up to 70 years old are accepted.",
        [
            {
                "target": "R1_age",
                "expr": "not (21 <= age <= 70)",
                "note": "At least 21 and at most 70 years old.",
            }
        ],
    ),
]


def scenario_by_id(scenario_id: str) -> Scenario:
    for scenario in SCENARIOS:
        if scenario.id == scenario_id:
            return scenario
    raise KeyError(scenario_id)
