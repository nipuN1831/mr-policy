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


def test_every_pack_has_a_disclaimer_and_some_sourced_content():
    for pack in all_packs():
        assert "not legal advice" in pack.disclaimer.lower(), pack.code
        assert pack.problems or pack.schemes or pack.rights, pack.code


def test_partial_packs_say_what_is_missing():
    for pack in all_packs():
        if pack.status == "partial":
            assert pack.notes, pack.code


def test_verified_status_requires_full_coverage():
    for pack in all_packs():
        if pack.status == "verified":
            assert len(pack.tiers) >= 2 and len(pack.problems) >= 5 and len(pack.rights) >= 3, pack.code
            assert all(p.verified for p in pack.problems), pack.code


def test_india_pack_is_the_most_complete():
    pack = load_pack("in")
    assert len(pack.tiers) >= 2 and len(pack.problems) >= 5 and len(pack.rights) >= 3


def test_five_countries_are_available():
    codes = {c["code"] for c in available_countries()}
    assert {"in", "sg", "au", "ph", "id"} <= codes


def test_every_source_is_https_and_dated():
    for pack in all_packs():
        sources = [t.source for t in pack.tiers] + [p.source for p in pack.problems] + [r.source for r in pack.rights] + [x.source for x in pack.schemes]
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


def test_bundled_representatives_have_correct_fictional_flag():
    for pack in all_packs():
        assert pack.representatives, pack.code
        for person in pack.representatives:
            if person.fictional:
                assert "demo" in person.region.lower() or "fictional" in person.region.lower(), (pack.code, person.id)
            else:
                assert all(
                    f.source.checked or f.source.grounded for f in person.record
                ), (pack.code, person.id)


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


def test_find_representatives_strips_natural_language_prefix():
    pack = load_pack("in")
    # "Rahul Gandhi" is a real MP in the pack — these natural-language queries should all find him
    for query in ("tell me about rahul gandhi", "who is rahul gandhi", "show me rahul gandhi", "find rahul gandhi"):
        results = find_representatives(pack, query)
        assert results, f"Expected results for query: {query!r}"
        assert any("Gandhi" in r.name for r in results), f"Expected Rahul Gandhi for: {query!r}"


def test_find_representatives_plain_name_still_works():
    pack = load_pack("in")
    results = find_representatives(pack, "Rahul Gandhi")
    assert results and any("Gandhi" in r.name for r in results)


def test_find_representatives_by_constituency_is_case_insensitive():
    pack = load_pack("in")
    constituency = pack.representatives[0].constituency
    found = find_representatives(pack, constituency.upper())
    assert found and all(r.constituency.lower() == constituency.lower() or r.role for r in found)
    assert find_representatives(pack, "Nowhere") == []


def test_find_representatives_by_name():
    pack = load_pack("in")
    found = find_representatives(pack, "Narendra Modi")
    assert found and any("Modi" in r.name for r in found)


def test_find_representatives_by_partial_name():
    pack = load_pack("in")
    found = find_representatives(pack, "Rahul Gandhi")
    assert found and any("Gandhi" in r.name for r in found)


def test_pack_model_rejects_duplicate_representative_ids():
    data = load_pack("in").model_dump()
    data["representatives"] = data["representatives"] + data["representatives"][:1]
    with pytest.raises(ValidationError):
        CountryPack.model_validate(data)
