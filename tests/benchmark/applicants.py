from policy_wind_tunnel.benchmark.models import Applicant

REQUIRED_DOCS = frozenset({"id_proof", "address_proof", "income_proof"})
SELF_EMPLOYED_DOCS = REQUIRED_DOCS | {"business_proof"}


def make(**overrides) -> Applicant:
    base = dict(
        age=35,
        employment="salaried",
        monthly_income=60000,
        business_vintage_months=None,
        credit_score=750,
        existing_obligations=5000,
        proposed_emi=10000,
        loan_amount=600000,
        documents=REQUIRED_DOCS,
        relationship_months=0,
        has_delinquency=False,
    )
    base.update(overrides)
    return Applicant(**base)


def low_income(**overrides) -> Applicant:
    base = dict(
        monthly_income=25000,
        existing_obligations=1000,
        proposed_emi=2000,
        loan_amount=100000,
    )
    base.update(overrides)
    return make(**base)


def self_employed(**overrides) -> Applicant:
    base = dict(
        employment="self_employed",
        monthly_income=35000,
        business_vintage_months=24,
        existing_obligations=1000,
        proposed_emi=2000,
        loan_amount=100000,
        documents=SELF_EMPLOYED_DOCS,
    )
    base.update(overrides)
    return make(**base)
