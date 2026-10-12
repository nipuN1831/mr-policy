import pytest
from pydantic import ValidationError

from policy_wind_tunnel.civic.lookup import find_problems, find_representatives
from policy_wind_tunnel.civic.models import CountryPack, Fact, Representative, Source
from policy_wind_tunnel.civic.packs import available_countries, load_pack

DATE = "2026-10-13"


def source(**overrides):
    base = dict(url="https://example.org/page", title="Page", as_of=DATE, checked=True)
    base.update(overrides)
    return Source(**base)


def rep(**overrides):
    base = dict(
        id="r1",
        name="Sample Member",
        role="Member of Parliament",
        body="Parliament",
        region="Demo State",
        constituency="Demo Constituency",
        fictional=True,
    )
    base.update(overrides)
    return Representative(**base)


def all_packs():
    return [load_pack(c["code"]) for c in available_countries()]


def test_at_least_one_country_is_available_and_listed_with_code_and_name():
    listing = available_countries()
    assert listing and all({"code", "name"} <= c.keys() for c in listing)
    assert len({c["code"] for c in listing}) == len(listing)


def test_unknown_country_raises_key_error():
    with pytest.raises(KeyError):
        load_pack("zz")


def test_every_pack_has_tiers_problems_rights_and_a_disclaimer():
    for pack in all_packs():
        assert len(pack.tiers) >= 2, pack.code
        assert len(pack.problems) >= 5, pack.code
        assert len(pack.rights) >= 3, pack.code
        assert "not legal advice" in pack.disclaimer.lower(), pack.code


def test_every_source_is_https_and_dated():
    for pack in all_packs():
        sources = [t.source for t in pack.tiers] + [p.source for p in pack.problems] + [r.source for r in pack.rights]
        for item in sources:
            assert item.url.startswith("https://"), (pack.code, item.url)
            assert len(item.as_of) == 10 and item.as_of[4] == "-", (pack.code, item.as_of)


def test_unverified_parts_must_be_named():
    for pack in all_packs():
        for problem in pack.problems:
            if not problem.verified:
                assert problem.unverified_parts, (pack.code, problem.id)
            assert len(problem.steps) >= 1, (pack.code, problem.id)


def test_problem_ids_are_unique_and_helplines_have_numbers():
    for pack in all_packs():
        ids = [p.id for p in pack.problems]
        assert len(ids) == len(set(ids)), pack.code
        for problem in pack.problems:
            for line in problem.helplines:
                assert line.number.strip(), (pack.code, problem.id)


def test_every_bundled_representative_is_fictional_and_labelled():
    for pack in all_packs():
        assert pack.representatives, pack.code
        for person in pack.representatives:
            assert person.fictional is True, (pack.code, person.id)
            assert "demo" in person.region.lower() or "fictional" in person.region.lower(), (pack.code, person.id)


def test_representative_cannot_carry_personal_fields():
    for field in ("phone", "address", "dob", "email", "assets", "criminal_cases"):
        with pytest.raises(ValidationError):
            rep(**{field: "x"})


def test_handles_must_be_usernames_not_urls_or_posts():
    assert rep(handles={"x": "demo_account"}).handles == {"x": "demo_account"}
    with pytest.raises(ValidationError):
        rep(handles={"x": "https://x.com/demo_account"})
    with pytest.raises(ValidationError):
        rep(handles={"x": "@demo account"})
    with pytest.raises(ValidationError):
        rep(handles={"tiktok": "demo"})


def test_a_real_person_needs_a_sourced_record_that_was_checked():
    with pytest.raises(ValidationError):
        rep(fictional=False)
    with pytest.raises(ValidationError):
        rep(fictional=False, record=[Fact(label="Terms", value="2", source=source(checked=False))])
    real = rep(fictional=False, record=[Fact(label="Terms", value="2", source=source())])
    assert real.fictional is False


def test_facts_cannot_contain_judgement_words():
    for word in ("corrupt", "best", "worst", "criminal"):
        with pytest.raises(ValidationError):
            Fact(label="Note", value=f"A {word} leader", source=source())


def test_find_problems_ranks_by_keyword_overlap():
    pack = load_pack("in")
    top = find_problems(pack, "my bank refused to refund a wrong charge")
    assert top and top[0].id == "bank_issue"


def test_find_problems_handles_empty_and_unrelated_text():
    pack = load_pack("in")
    assert find_problems(pack, "") == []
    assert find_problems(pack, "zzzz qqqq") == []


def test_find_problems_limits_results():
    pack = load_pack("in")
    assert len(find_problems(pack, "complaint government bank consumer rights", limit=2)) <= 2


def test_find_representatives_by_constituency_is_case_insensitive():
    pack = load_pack("in")
    constituency = pack.representatives[0].constituency
    found = find_representatives(pack, constituency.upper())
    assert found and all(r.constituency.lower() == constituency.lower() or r.role for r in found)
    assert find_representatives(pack, "Nowhere") == []


def test_pack_model_rejects_duplicate_representative_ids():
    data = load_pack("in").model_dump()
    data["representatives"] = data["representatives"] + data["representatives"][:1]
    with pytest.raises(ValidationError):
        CountryPack.model_validate(data)
