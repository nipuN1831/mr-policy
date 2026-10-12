from policy_wind_tunnel.civic import scheme_texts as texts
from policy_wind_tunnel.civic.eligibility import SchemeSpec
from policy_wind_tunnel.contract.models import Contract


def _rule(rule_id, clause, quote, when, outcome, reason=None):
    return {"id": rule_id, "clause": clause, "source_quote": quote, "when": when, "outcome": outcome, "reason": reason}


def _int(name, description, minimum=0, maximum=None, nullable=False, typical=None, changeable=True, cost=1):
    return {
        "name": name, "kind": "int", "min": minimum, "max": maximum, "nullable": nullable, "typical": typical,
        "description": description, "changeable": changeable, "change_cost": cost,
    }


def _bool(name, description, typical=False, changeable=True, cost=1):
    return {"name": name, "kind": "bool", "typical": typical, "description": description, "changeable": changeable, "change_cost": cost}


SILVER_CONTRACT = {
    "name": "sg_silver_support",
    "description": "Silver Support Scheme, encoded from the CPF Board page last updated 17 Sep 2026.",
    "outcomes": ["PAY_1080", "PAY_860", "PAY_650", "PAY_430", "PAY_540", "PAY_325", "PAY_215", "NOT_ELIGIBLE"],
    "fields": [
        _bool("citizen", "I am a Singapore Citizen", True, False),
        _int("age", "My age", 0, 120, typical=70, changeable=False),
        _bool("self_employed", "I was self-employed or a platform worker", False, False),
        _int("cpf_by_55", "Total CPF contributions I made by age 55 (S$)", nullable=True, typical=100000, changeable=False),
        _int("trade_income_45_54", "Average annual net trade income at ages 45 to 54 (S$)", nullable=True, changeable=False),
        {
            "name": "housing", "kind": "enum", "values": ["hdb_1_2", "hdb_3", "hdb_4", "hdb_5", "other"], "typical": "hdb_4",
            "description": "The home I live in", "changeable": True, "change_cost": 6,
            "labels": {"hdb_1_2": "1- or 2-room HDB flat", "hdb_3": "3-room HDB flat", "hdb_4": "4-room HDB flat", "hdb_5": "5-room HDB flat", "other": "Other housing"},
        },
        _bool("owns_big_property", "I or my spouse own a 5-room or larger HDB flat, private property or multiple properties", False, True, 8),
        _int("pchi", "Monthly household income per person (S$)", typical=1400, cost=1),
    ],
    "derived": [
        {"name": "wage_ok", "clause": "Criterion 1", "source_quote": "The total CPF contributions you made by age 55 is up to $140,000.",
         "expr": "(cpf_by_55 is not None and cpf_by_55 <= 140000) if not self_employed else (trade_income_45_54 is not None and trade_income_45_54 <= 27600)"},
        {"name": "low_band", "clause": "Payout table", "source_quote": "$1,080 if PCHI is up to $1,500", "expr": "pchi <= 1500"},
    ],
    "stages": [
        {
            "name": "criteria",
            "mode": "collect",
            "rules": [
                _rule("S_citizen", "Who qualifies", "if you're a Singapore Citizen aged 65 and above, you'll automatically qualify", "not citizen", "NOT_ELIGIBLE", "CITIZEN"),
                _rule("S_age", "Who qualifies", "aged 65 and above", "age < 65", "NOT_ELIGIBLE", "AGE"),
                _rule("S_wages", "Criterion 1", "The total CPF contributions you made by age 55 is up to $140,000.", "not wage_ok", "NOT_ELIGIBLE", "WAGES"),
                _rule("S_housing", "Criterion 2", "You live in a 1- to 5-room HDB flat.", 'housing == "other"', "NOT_ELIGIBLE", "HOUSING"),
                _rule("S_property", "Criterion 2", "You or your spouse do not own a 5-room or larger HDB flat, private property or multiple properties.", "owns_big_property", "NOT_ELIGIBLE", "PROPERTY"),
                _rule("S_income", "Criterion 3", "You live in a household with a per capita household income of up to $2,300.", "pchi > 2300", "NOT_ELIGIBLE", "INCOME"),
            ],
        },
        {
            "name": "payout",
            "mode": "first_match",
            "rules": [
                _rule("P_12_low", "Payout table", "1- and 2-room flat: $1,080 if PCHI is up to $1,500", 'housing == "hdb_1_2" and low_band', "PAY_1080"),
                _rule("P_12_high", "Payout table", "$540 if above $1,500 up to $2,300", 'housing == "hdb_1_2"', "PAY_540"),
                _rule("P_3_low", "Payout table", "3-room flat: $860 if PCHI is up to $1,500", 'housing == "hdb_3" and low_band', "PAY_860"),
                _rule("P_3_high", "Payout table", "$430 if above $1,500 up to $2,300", 'housing == "hdb_3"', "PAY_430"),
                _rule("P_4_low", "Payout table", "4-room flat: $650 if PCHI is up to $1,500", 'housing == "hdb_4" and low_band', "PAY_650"),
                _rule("P_4_high", "Payout table", "$325 if above $1,500 up to $2,300", 'housing == "hdb_4"', "PAY_325"),
                _rule("P_5_low", "Payout table", "5-room flat: $430 if PCHI is up to $1,500", 'housing == "hdb_5" and low_band', "PAY_430"),
                _rule("P_5_high", "Payout table", "$215 if above $1,500 up to $2,300", "True", "PAY_215"),
            ],
        },
    ],
    "ambiguities": [
        {"id": "SA1", "clause": "Who qualifies", "question": "How is household income per person measured?",
         "resolution": "Assumed to be the monthly per capita household income the person enters; the official assessment may differ.", "status": "proposed"},
        {"id": "SA2", "clause": "Criterion 1", "question": "Which wage test applies?",
         "resolution": "Employees are tested on CPF contributions by 55; the self-employed on average net trade income at 45 to 54.", "status": "proposed"},
        {"id": "SA3", "clause": "Payout table", "question": "Does a person who qualifies need to apply?",
         "resolution": "Not covered by this check. Eligibility is reviewed by CPF each year according to secondary sources, not verified here.", "status": "proposed"},
    ],
}

LEGAL_CONTRACT = {
    "name": "sg_legal_aid_means",
    "description": "Legal Aid Bureau Means Test from 1 Oct 2026, encoded from the page last updated 30 Sep 2026.",
    "outcomes": ["MEANS_TEST_PASSED", "MEANS_TEST_FAILED"],
    "fields": [
        _int("age", "My age", 0, 120, typical=45, changeable=False),
        _int("pchi_12m", "Average monthly household income per person over the last 12 months (S$)", typical=1500),
        _int("annual_value", "Annual Value of the home I own (S$)", typical=15000, cost=4),
        _int("savings", "Savings and non-CPF investments (S$)", typical=8000, cost=2),
        _bool("owns_other_property", "I hold property other than my home", False, True, 8),
    ],
    "derived": [
        {"name": "savings_limit", "clause": "Savings", "source_quote": "$12,000 or lower if under 60. $42,000 or lower if aged 60 and above.", "expr": "42000 if age >= 60 else 12000"},
    ],
    "stages": [
        {
            "name": "means",
            "mode": "collect",
            "rules": [
                _rule("L_income", "Income", "must be $1,650 or lower for the last 12 months prior to the application", "pchi_12m > 1650", "MEANS_TEST_FAILED", "INCOME"),
                _rule("L_home", "Home value", "Annual Value of the owned residence must be $21,000 or lower.", "annual_value > 21000", "MEANS_TEST_FAILED", "HOME_VALUE"),
                _rule("L_savings", "Savings", "$12,000 or lower if under 60. $42,000 or lower if aged 60 and above.", "savings > savings_limit", "MEANS_TEST_FAILED", "SAVINGS"),
                _rule("L_property", "Property", "The applicant may not hold any property other than their residence.", "owns_other_property", "MEANS_TEST_FAILED", "PROPERTY"),
            ],
        },
        {"name": "result", "mode": "first_match", "rules": [_rule("L_pass", "Means Test", "Legal Aid requires the Means and Merits Tests.", "True", "MEANS_TEST_PASSED")]},
    ],
    "ambiguities": [
        {"id": "LA1", "clause": "Income", "question": "Is the income limit gross or net?",
         "resolution": "The page says per capita gross monthly household income; the person enters that figure.", "status": "proposed"},
        {"id": "LA2", "clause": "Means Test", "question": "Does passing the Means Test mean legal aid is granted?",
         "resolution": "No. Legal Aid also needs the Merits Test, and Singapore Citizens and PRs only, per secondary sources.", "status": "proposed"},
    ],
}

PMUY_CONTRACT = {
    "name": "in_pmuy",
    "description": "PM Ujjwala Yojana 2.0 eligibility, encoded from the pmuy.gov.in page.",
    "outcomes": ["ELIGIBLE", "NOT_ELIGIBLE"],
    "fields": [
        {"name": "gender", "kind": "enum", "values": ["female", "male", "other"], "typical": "female", "description": "My gender", "changeable": False,
         "labels": {"female": "Woman", "male": "Man", "other": "Other"}},
        _int("age", "My age", 0, 120, typical=30, changeable=False),
        _bool("has_other_lpg", "My household already has an LPG connection from any oil marketing company", False, True, 3),
        _bool("poor_declaration", "I can submit a deprivation declaration for my household", True, True, 2),
    ],
    "derived": [],
    "stages": [
        {
            "name": "criteria",
            "mode": "collect",
            "rules": [
                _rule("U_woman", "Applicant", "The applicant must be a woman", 'gender != "female"', "NOT_ELIGIBLE", "WOMAN"),
                _rule("U_age", "Applicant", "who has attained 18 years of age", "age < 18", "NOT_ELIGIBLE", "AGE"),
                _rule("U_lpg", "Household", "There should be no other LPG connection from any Oil Marketing Company (OMC) within the same household.", "has_other_lpg", "NOT_ELIGIBLE", "LPG"),
                _rule("U_poor", "Household", "The adult woman must belong to a poor household based on submission of a deprivation declaration (as per prescribed format).", "not poor_declaration", "NOT_ELIGIBLE", "POOR"),
            ],
        },
        {"name": "result", "mode": "first_match", "rules": [_rule("U_ok", "Applicant", "The applicant must be a woman", "True", "ELIGIBLE")]},
    ],
    "ambiguities": [
        {"id": "PM1", "clause": "Household", "question": "Who decides whether a household is poor?",
         "resolution": "The page bases it on a submitted deprivation declaration; the oil company and officials verify it.", "status": "proposed"},
    ],
}

SILVER_LABELS = {
    "PAY_1080": "Silver Support: S$1,080 per quarter",
    "PAY_540": "Silver Support: S$540 per quarter",
    "PAY_860": "Silver Support: S$860 per quarter",
    "PAY_430": "Silver Support: S$430 per quarter",
    "PAY_650": "Silver Support: S$650 per quarter",
    "PAY_325": "Silver Support: S$325 per quarter",
    "PAY_215": "Silver Support: S$215 per quarter",
    "NOT_ELIGIBLE": "Not eligible on the published criteria",
}


def specs() -> dict[str, SchemeSpec]:
    silver = Contract.model_validate(SILVER_CONTRACT)
    legal = Contract.model_validate(LEGAL_CONTRACT)
    pmuy = Contract.model_validate(PMUY_CONTRACT)
    return {
        "sg_silver_support": SchemeSpec(
            "sg_silver_support", "sg", "Silver Support Scheme", silver, texts.SILVER_TEXT,
            [o for o in silver.outcomes if o != "NOT_ELIGIBLE"], SILVER_LABELS, texts.SILVER_SOURCE,
            {"CITIZEN": "Not a Singapore Citizen", "AGE": "Under 65", "WAGES": "Lifetime wages above the limit", "HOUSING": "Not in a 1- to 5-room HDB flat",
             "PROPERTY": "Owns a 5-room or larger flat or other property", "INCOME": "Household income per person above S$2,300"},
        ),
        "sg_legal_aid_means": SchemeSpec(
            "sg_legal_aid_means", "sg", "Legal Aid Bureau Means Test", legal, texts.LEGAL_TEXT, ["MEANS_TEST_PASSED"],
            {"MEANS_TEST_PASSED": "Passes the Means Test. Legal Aid also needs the Merits Test, so this is not an approval.",
             "MEANS_TEST_FAILED": "Does not pass the Means Test"},
            texts.LEGAL_SOURCE,
            {"INCOME": "Income above S$1,650 per person", "HOME_VALUE": "Home Annual Value above S$21,000", "SAVINGS": "Savings above the limit", "PROPERTY": "Holds other property"},
        ),
        "in_pmuy": SchemeSpec(
            "in_pmuy", "in", "Ujjwala (PMUY 2.0)", pmuy, texts.PMUY_TEXT, ["ELIGIBLE"],
            {"ELIGIBLE": "Meets the published criteria", "NOT_ELIGIBLE": "Does not meet the published criteria"}, texts.PMUY_SOURCE,
            {"WOMAN": "Applicant must be a woman", "AGE": "Under 18", "LPG": "Household already has an LPG connection", "POOR": "No deprivation declaration"},
        ),
    }
