import pytest

from policy_wind_tunnel.civic.counterfactual import nearest_changes
from policy_wind_tunnel.civic.eligibility import check, get_scheme
from policy_wind_tunnel.contract.evaluator import evaluate
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.benchmark.samples import typical_inputs

SILVER = "sg_silver_support"


def silver(**overrides):
    base = dict(
        citizen=True, age=70, self_employed=False, cpf_by_55=100000, trade_income_45_54=None,
        housing="hdb_4", owns_big_property=False, pchi=1400,
    )
    base.update(overrides)
    return base


def scheme():
    return get_scheme(SILVER)


def test_a_small_income_overshoot_gets_a_one_field_answer():
    result = nearest_changes(scheme(), silver(pchi=2400))
    best = result.alternatives[0]
    assert best.changes == [{"field": "pchi", "from": 2400, "to": 2300}]
    assert best.outcome == "PAY_325"


def test_every_alternative_is_verified_by_the_real_evaluator():
    result = nearest_changes(scheme(), silver(pchi=2400, housing="other", owns_big_property=True))
    assert result.alternatives
    for alt in result.alternatives:
        changed = {**silver(pchi=2400, housing="other", owns_big_property=True)}
        for change in alt.changes:
            changed[change["field"]] = change["to"]
        assert evaluate(scheme().contract, changed)["outcome"] == alt.outcome
        assert alt.outcome != "NOT_ELIGIBLE"


def lending_spec():
    from policy_wind_tunnel.civic.eligibility import SchemeSpec

    return SchemeSpec(
        id="lend", country="in", name="Lending", contract=LENDING_CONTRACT, policy_text="x",
        favourable=["APPROVE"], outcome_labels={}, source={"url": "https://example.org", "title": "t", "as_of": "2026-10-13", "checked": True},
    )


def test_alternatives_use_distinct_sets_of_changed_fields():
    applicant = typical_inputs(existing_obligations=30000, proposed_emi=10000)
    result = nearest_changes(lending_spec(), applicant, limit=3)
    sets = [frozenset(c["field"] for c in a.changes) for a in result.alternatives]
    assert len(sets) == len(set(sets)) and len(sets) >= 2
    assert not any(a < b for a in sets for b in sets)


def test_cheap_numeric_changes_are_preferred_to_life_changes():
    result = nearest_changes(scheme(), silver(pchi=2400, housing="other"))
    assert {c["field"] for c in result.alternatives[0].changes} == {"pchi", "housing"}


def test_fields_a_person_cannot_change_are_never_suggested():
    result = nearest_changes(scheme(), silver(pchi=2400, cpf_by_55=150000))
    for alt in result.alternatives:
        assert not {c["field"] for c in alt.changes} & {"age", "citizen", "self_employed", "cpf_by_55", "trade_income_45_54"}


def test_when_only_an_unchangeable_field_blocks_the_answer_it_says_so():
    result = nearest_changes(scheme(), silver(age=63))
    assert result.alternatives == [] and result.blocked_by == ["age"]
    assert result.already_met is False


def test_blocked_by_lists_every_unchangeable_field_that_would_need_to_change():
    result = nearest_changes(scheme(), silver(age=63, cpf_by_55=150000))
    assert result.alternatives == [] and result.blocked_by == ["age", "cpf_by_55"]


def test_an_already_eligible_applicant_gets_no_alternatives_by_default():
    result = nearest_changes(scheme(), silver())
    assert result.already_met is True and result.alternatives == []


def test_an_eligible_applicant_can_ask_how_to_reach_a_higher_payout():
    result = nearest_changes(scheme(), silver(pchi=2000), targets=["PAY_650"])
    assert result.alternatives[0].changes == [{"field": "pchi", "from": 2000, "to": 1500}]
    assert result.alternatives[0].outcome == "PAY_650"


def test_single_field_answer_is_the_true_minimum_by_brute_force():
    locked = [f.name for f in scheme().contract.fields if f.name != "pchi"]
    for start in (2301, 2400, 3100, 5000):
        result = nearest_changes(scheme(), silver(pchi=start), lock=locked)
        best = result.alternatives[0].changes[0]["to"]
        brute = min(
            (v for v in range(0, 6001) if evaluate(scheme().contract, silver(pchi=v))["outcome"] != "NOT_ELIGIBLE"),
            key=lambda v: abs(v - start),
        )
        assert abs(best - start) == abs(brute - start)


def test_locking_fields_restricts_the_search():
    result = nearest_changes(scheme(), silver(pchi=2400), lock=["pchi"])
    assert all("pchi" not in {c["field"] for c in a.changes} for a in result.alternatives)


def test_works_on_the_lending_contract_too():
    from policy_wind_tunnel.civic.eligibility import SchemeSpec

    spec = SchemeSpec(
        id="lend", country="in", name="Lending", contract=LENDING_CONTRACT, policy_text="x",
        favourable=["APPROVE"], outcome_labels={}, source={"url": "https://example.org", "title": "t", "as_of": "2026-10-13", "checked": True},
    )
    applicant = typical_inputs(existing_obligations=30000, proposed_emi=10000)
    assert evaluate(LENDING_CONTRACT, applicant)["outcome"] == "REJECT"
    result = nearest_changes(spec, applicant)
    assert result.alternatives
    for alt in result.alternatives:
        changed = dict(applicant)
        for change in alt.changes:
            changed[change["field"]] = change["to"]
        assert evaluate(LENDING_CONTRACT, changed)["outcome"] == "APPROVE"


def test_unknown_target_outcome_is_rejected():
    with pytest.raises(ValueError):
        nearest_changes(scheme(), silver(pchi=2400), targets=["NOPE"])


def test_result_is_json_ready():
    result = nearest_changes(scheme(), silver(pchi=2400)).as_dict()
    assert {"alternatives", "blocked_by", "already_met", "current_outcome"} <= result.keys()
    assert result["alternatives"][0]["summary"]
    assert result["current_outcome"] == check(SILVER, silver(pchi=2400))["outcome"]
