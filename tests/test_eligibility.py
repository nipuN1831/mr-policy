import pytest

from policy_wind_tunnel.civic.eligibility import SchemeError, check, form_spec, get_scheme, list_schemes
from policy_wind_tunnel.civic.packs import available_countries, load_pack
from policy_wind_tunnel.contract.evaluator import ContractError
from policy_wind_tunnel.adversary.symbolic import SymbolicContract

SILVER = "sg_silver_support"
LEGAL = "sg_legal_aid_means"
PMUY = "in_pmuy"


def silver(**overrides):
    base = dict(
        citizen=True,
        age=70,
        self_employed=False,
        cpf_by_55=100000,
        trade_income_45_54=None,
        housing="hdb_4",
        owns_big_property=False,
        pchi=1400,
    )
    base.update(overrides)
    return base


def legal(**overrides):
    base = dict(age=45, pchi_12m=1500, annual_value=15000, savings=8000, owns_other_property=False)
    base.update(overrides)
    return base


def pmuy(**overrides):
    base = dict(gender="female", age=30, has_other_lpg=False, poor_declaration=True)
    base.update(overrides)
    return base


def outcome(scheme, inputs):
    return check(scheme, inputs)["outcome"]


def reasons(scheme, inputs):
    return check(scheme, inputs)["reasons"]


def test_registry_lists_schemes_with_their_country():
    listing = list_schemes()
    ids = {s["id"] for s in listing}
    assert {SILVER, LEGAL, PMUY} <= ids
    assert all({"id", "country", "name", "self_check"} <= s.keys() for s in listing)


def test_every_registered_scheme_appears_in_its_country_pack():
    for spec in list_schemes():
        if spec["self_check"]:
            pack = load_pack(spec["country"])
            assert spec["id"] in {s.id for s in pack.schemes}, spec["id"]


def test_every_pack_scheme_is_either_self_checkable_or_labelled_not():
    listed = {s["id"]: s for s in list_schemes()}
    for country in available_countries():
        for scheme in load_pack(country["code"]).schemes:
            assert scheme.id in listed, scheme.id


def test_unknown_scheme_raises():
    with pytest.raises(SchemeError):
        get_scheme("nope")
    with pytest.raises(SchemeError):
        check("nope", {})


def test_all_scheme_contracts_are_complete_and_reachable():
    for spec in list_schemes():
        if not spec["self_check"]:
            continue
        symbolic = SymbolicContract(get_scheme(spec["id"]).contract)
        assert symbolic.find_uncovered_input() is None, spec["id"]
        assert [r for r in symbolic.rule_ids() if not symbolic.can_fire(r)] == [], spec["id"]


def test_every_rule_quote_appears_verbatim_in_the_scheme_text():
    for spec in list_schemes():
        if not spec["self_check"]:
            continue
        scheme = get_scheme(spec["id"])
        text = " ".join(scheme.policy_text.split())
        for _, rule in scheme.contract.all_rules():
            if rule.source_quote:
                assert " ".join(rule.source_quote.split()) in text, (spec["id"], rule.id)


def test_every_field_has_a_citizen_readable_label():
    for spec in list_schemes():
        if spec["self_check"]:
            for field in get_scheme(spec["id"]).contract.fields:
                assert field.description, (spec["id"], field.name)


@pytest.mark.parametrize(
    "housing,low,high",
    [("hdb_1_2", "PAY_1080", "PAY_540"), ("hdb_3", "PAY_860", "PAY_430"), ("hdb_4", "PAY_650", "PAY_325"), ("hdb_5", "PAY_430", "PAY_215")],
)
def test_silver_support_payout_table(housing, low, high):
    assert outcome(SILVER, silver(housing=housing, pchi=1500)) == low
    assert outcome(SILVER, silver(housing=housing, pchi=1501)) == high
    assert outcome(SILVER, silver(housing=housing, pchi=2300)) == high


def test_silver_support_income_ceiling_is_inclusive():
    assert outcome(SILVER, silver(pchi=2300)) == "PAY_325"
    result = check(SILVER, silver(pchi=2301))
    assert result["outcome"] == "NOT_ELIGIBLE" and result["reasons"] == ["INCOME"]


def test_silver_support_age_and_citizenship():
    assert outcome(SILVER, silver(age=65)) == "PAY_650"
    assert reasons(SILVER, silver(age=64)) == ["AGE"]
    assert reasons(SILVER, silver(citizen=False)) == ["CITIZEN"]


def test_silver_support_lifetime_wage_limit():
    assert outcome(SILVER, silver(cpf_by_55=140000)) == "PAY_650"
    assert reasons(SILVER, silver(cpf_by_55=140001)) == ["WAGES"]
    assert reasons(SILVER, silver(cpf_by_55=None)) == ["WAGES"]


def test_silver_support_self_employed_uses_trade_income():
    ok = silver(self_employed=True, cpf_by_55=None, trade_income_45_54=27600)
    assert outcome(SILVER, ok) == "PAY_650"
    assert reasons(SILVER, {**ok, "trade_income_45_54": 27601}) == ["WAGES"]
    assert reasons(SILVER, {**ok, "trade_income_45_54": None}) == ["WAGES"]


def test_silver_support_housing_and_property():
    assert reasons(SILVER, silver(housing="other")) == ["HOUSING"]
    assert reasons(SILVER, silver(owns_big_property=True)) == ["PROPERTY"]


def test_silver_support_reports_every_failing_criterion_in_order():
    result = check(SILVER, silver(age=60, pchi=3000, housing="other", cpf_by_55=200000))
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert result["reasons"] == ["AGE", "WAGES", "HOUSING", "INCOME"]


def test_silver_support_assumptions_are_listed_as_assumptions():
    assumptions = get_scheme(SILVER).contract.ambiguities
    assert assumptions and all(a.status == "proposed" for a in assumptions)


def test_check_returns_quotes_and_labels_for_the_rules_that_fired():
    result = check(SILVER, silver(pchi=2400))
    clause = result["clauses"][0]
    assert clause["quote"] and "2,300" in clause["quote"]
    assert clause["rule_id"] and clause["clause"]
    assert result["outcome_label"] and result["source"]["url"].startswith("https://")
    assert "not an official decision" in result["disclaimer"].lower()


def test_check_for_an_eligible_applicant_quotes_the_payout_row():
    result = check(SILVER, silver())
    assert result["outcome"] == "PAY_650" and "650" in result["outcome_label"]
    assert result["clauses"]


@pytest.mark.parametrize(
    "overrides,expected",
    [({}, "MEANS_TEST_PASSED"), ({"pchi_12m": 1650}, "MEANS_TEST_PASSED"), ({"pchi_12m": 1651}, "MEANS_TEST_FAILED")],
)
def test_legal_aid_income_limit(overrides, expected):
    assert outcome(LEGAL, legal(**overrides)) == expected


def test_legal_aid_home_value_and_property():
    assert outcome(LEGAL, legal(annual_value=21000)) == "MEANS_TEST_PASSED"
    assert reasons(LEGAL, legal(annual_value=21001)) == ["HOME_VALUE"]
    assert reasons(LEGAL, legal(owns_other_property=True)) == ["PROPERTY"]


def test_legal_aid_savings_limit_depends_on_age():
    assert outcome(LEGAL, legal(age=59, savings=12000)) == "MEANS_TEST_PASSED"
    assert reasons(LEGAL, legal(age=59, savings=12001)) == ["SAVINGS"]
    assert outcome(LEGAL, legal(age=60, savings=42000)) == "MEANS_TEST_PASSED"
    assert reasons(LEGAL, legal(age=60, savings=42001)) == ["SAVINGS"]


def test_legal_aid_label_says_the_means_test_is_not_approval():
    assert "merits" in check(LEGAL, legal())["outcome_label"].lower()


def test_pmuy_rules():
    assert outcome(PMUY, pmuy()) == "ELIGIBLE"
    assert outcome(PMUY, pmuy(age=18)) == "ELIGIBLE"
    assert reasons(PMUY, pmuy(age=17)) == ["AGE"]
    assert reasons(PMUY, pmuy(gender="male")) == ["WOMAN"]
    assert reasons(PMUY, pmuy(has_other_lpg=True)) == ["LPG"]
    assert reasons(PMUY, pmuy(poor_declaration=False)) == ["POOR"]


def test_invalid_inputs_are_rejected():
    with pytest.raises(ContractError):
        check(SILVER, silver(housing="castle"))
    with pytest.raises(ContractError):
        check(SILVER, silver(age="seventy"))
    missing = silver()
    del missing["pchi"]
    with pytest.raises(ContractError):
        check(SILVER, missing)


def test_form_spec_describes_every_field_for_the_page():
    spec = form_spec(SILVER)
    names = [f["name"] for f in spec["fields"]]
    assert "pchi" in names and "housing" in names
    housing = next(f for f in spec["fields"] if f["name"] == "housing")
    assert housing["kind"] == "enum" and len(housing["options"]) == 5 and all(o["label"] for o in housing["options"])
    assert all(f["label"] for f in spec["fields"])
    assert spec["policy_text"] and spec["source"]["url"].startswith("https://")
    assert isinstance(spec["assumptions"], list) and spec["assumptions"]
    assert {"id", "name", "country"} <= spec.keys()


def test_form_spec_marks_fields_a_person_cannot_change():
    fields = {f["name"]: f for f in form_spec(SILVER)["fields"]}
    assert fields["age"]["changeable"] is False and fields["pchi"]["changeable"] is True
