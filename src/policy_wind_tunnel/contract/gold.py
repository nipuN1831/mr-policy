from policy_wind_tunnel.contract.models import Contract

SELF_EMPLOYED_QUOTE = "must be at least 35,000\nand the business must be at least 24 months old."

GOLD_CONTRACT_DATA = {
    "name": "retail_lending_eligibility_v1",
    "description": "Gold contract for the fictional retail lending policy, written by hand from the policy text.",
    "outcomes": ["APPROVE", "REJECT", "REFER", "INCOMPLETE"],
    "fields": [
        {"name": "age", "kind": "int", "min": 0, "max": 120},
        {"name": "employment", "kind": "enum", "values": ["salaried", "self_employed"]},
        {"name": "monthly_income", "kind": "int", "min": 0},
        {"name": "business_vintage_months", "kind": "int", "nullable": True, "min": 0},
        {"name": "credit_score", "kind": "int", "nullable": True, "min": 300, "max": 900},
        {"name": "existing_obligations", "kind": "int", "min": 0},
        {"name": "proposed_emi", "kind": "int", "min": 0},
        {"name": "loan_amount", "kind": "int", "min": 0},
        {
            "name": "documents",
            "kind": "set",
            "values": ["id_proof", "address_proof", "income_proof", "business_proof"],
        },
        {"name": "relationship_months", "kind": "int", "min": 0},
        {"name": "has_delinquency", "kind": "bool"},
    ],
    "derived": [
        {
            "name": "docs_ok",
            "expr": (
                '"id_proof" in documents and "address_proof" in documents and "income_proof" in documents'
                ' and (employment != "self_employed" or "business_proof" in documents)'
            ),
            "clause": "L2",
            "source_quote": "ID proof, address proof and income proof are mandatory.",
        },
        {"name": "obligations", "expr": "existing_obligations + proposed_emi", "clause": "L4"},
        {
            "name": "exception_applies",
            "expr": "relationship_months >= 24 and not has_delinquency",
            "clause": "L7",
            "source_quote": "relationship of at least 24 months and no delinquency",
        },
        {
            "name": "approve_at",
            "expr": "680 if exception_applies else 700",
            "clause": "L7",
            "source_quote": "both L6 score thresholds lowered by 20 points",
        },
        {
            "name": "review_at",
            "expr": "630 if exception_applies else 650",
            "clause": "L7",
            "source_quote": "both L6 score thresholds lowered by 20 points",
        },
    ],
    "stages": [
        {
            "name": "completeness",
            "mode": "first_match",
            "rules": [
                {
                    "id": "R2_docs",
                    "clause": "L2",
                    "source_quote": "If any mandatory document is missing, the application is INCOMPLETE (reason DOCS)",
                    "when": "not docs_ok",
                    "outcome": "INCOMPLETE",
                    "reason": "DOCS",
                }
            ],
        },
        {
            "name": "eligibility",
            "mode": "collect",
            "rules": [
                {
                    "id": "R1_age",
                    "clause": "L1",
                    "source_quote": "at least 21 and at most 65 years old",
                    "when": "not (21 <= age <= 65)",
                    "outcome": "REJECT",
                    "reason": "AGE",
                },
                {
                    "id": "R3a_income_salaried",
                    "clause": "L3",
                    "source_quote": "verified monthly income must be at least 25,000",
                    "when": 'employment != "self_employed" and monthly_income < 25000',
                    "outcome": "REJECT",
                    "reason": "INCOME",
                },
                {
                    "id": "R3b_income_self_employed",
                    "clause": "L3",
                    "source_quote": SELF_EMPLOYED_QUOTE,
                    "when": (
                        'employment == "self_employed" and (monthly_income < 35000'
                        " or business_vintage_months is None or business_vintage_months < 24)"
                    ),
                    "outcome": "REJECT",
                    "reason": "INCOME",
                },
                {
                    "id": "R4_dti",
                    "clause": "L4",
                    "source_quote": "must not exceed 45%",
                    "when": "monthly_income <= 0 or obligations * 100 > 45 * monthly_income",
                    "outcome": "REJECT",
                    "reason": "DTI",
                },
                {
                    "id": "R5_cap",
                    "clause": "L5",
                    "source_quote": "must not exceed 20 times verified monthly income",
                    "when": "loan_amount > 20 * monthly_income",
                    "outcome": "REJECT",
                    "reason": "CAP",
                },
            ],
        },
        {
            "name": "score",
            "mode": "first_match",
            "rules": [
                {
                    "id": "R6a_no_score",
                    "clause": "L6",
                    "source_quote": "Score missing: REFER to manual review (reason NO_SCORE).",
                    "when": "credit_score is None",
                    "outcome": "REFER",
                    "reason": "NO_SCORE",
                },
                {
                    "id": "R6b_approve",
                    "clause": "L6",
                    "source_quote": "Score at least 700: APPROVE.",
                    "when": "credit_score >= approve_at",
                    "outcome": "APPROVE",
                },
                {
                    "id": "R6c_review",
                    "clause": "L6",
                    "source_quote": "Score from 650 to 699: REFER to manual review (reason SCORE_REVIEW).",
                    "when": "credit_score >= review_at",
                    "outcome": "REFER",
                    "reason": "SCORE_REVIEW",
                },
                {
                    "id": "R6d_reject",
                    "clause": "L6",
                    "source_quote": "Score below 650: REJECT (reason SCORE).",
                    "when": "True",
                    "outcome": "REJECT",
                    "reason": "SCORE",
                },
            ],
        },
    ],
    "ambiguities": [
        {
            "id": "A1",
            "clause": "L4",
            "question": "Is a debt-to-income ratio of exactly 45% acceptable?",
            "resolution": "Yes. The policy says 'must not exceed 45%', so exactly 45% passes.",
            "status": "approved",
        },
        {
            "id": "A2",
            "clause": "L4",
            "question": "What happens to the debt-to-income check when verified monthly income is zero?",
            "resolution": "The ratio is undefined, so the DTI check fails.",
            "status": "approved",
        },
        {
            "id": "A3",
            "clause": "L7",
            "question": "Does the existing-customer exception need both 24 months and no delinquency?",
            "resolution": "Yes. Both conditions are required, and a delinquency of any age disqualifies.",
            "status": "approved",
        },
        {
            "id": "A4",
            "clause": "L3",
            "question": "Is a self-employed applicant with unknown business age treated as meeting the 24-month rule?",
            "resolution": "No. Unknown business age fails the income rule.",
            "status": "approved",
        },
    ],
}

LENDING_CONTRACT = Contract.model_validate(GOLD_CONTRACT_DATA)
