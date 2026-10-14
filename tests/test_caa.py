"""Tests for CAA 2019 eligibility scheme."""
import pytest
from policy_wind_tunnel.civic.eligibility import check, form_spec, list_schemes, NotCheckable

SCHEME = "in_caa_2019"

# --- scheme is discoverable ---

def test_caa_appears_in_list():
    ids = [s["id"] for s in list_schemes()]
    assert SCHEME in ids

def test_caa_is_india():
    schemes = {s["id"]: s for s in list_schemes()}
    assert schemes[SCHEME]["country"] == "in"

# --- clear ELIGIBLE cases ---

def test_hindu_from_pakistan_entered_2010_5yr_residency_is_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "ELIGIBLE"

def test_sikh_from_afghanistan_entered_2014_eligible():
    result = check(SCHEME, {
        "religion": "sikh",
        "origin_country": "afghanistan",
        "entered_india_year": 2014,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "ELIGIBLE"

def test_christian_from_bangladesh_eligible():
    result = check(SCHEME, {
        "religion": "christian",
        "origin_country": "bangladesh",
        "entered_india_year": 2012,
        "years_in_india": 7,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "ELIGIBLE"

def test_buddhist_jain_parsi_all_eligible():
    for religion in ("buddhist", "jain", "parsi"):
        result = check(SCHEME, {
            "religion": religion,
            "origin_country": "pakistan",
            "entered_india_year": 2010,
            "years_in_india": 6,
            "inner_line_state": False,
            "sixth_schedule_area": False,
        })
        assert result["outcome"] == "ELIGIBLE", f"{religion} should be eligible"

# --- clear NOT_ELIGIBLE cases ---

def test_muslim_from_pakistan_not_eligible():
    result = check(SCHEME, {
        "religion": "muslim",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "RELIGION" in result["reasons"]

def test_hindu_from_other_country_not_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "other",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "COUNTRY" in result["reasons"]

def test_entered_after_cutoff_not_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2015,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "ENTRY_DATE" in result["reasons"]

def test_entered_exactly_on_cutoff_2014_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2014,
        "years_in_india": 7,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "ELIGIBLE"

def test_inner_line_state_not_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": True,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "INNER_LINE" in result["reasons"]

def test_sixth_schedule_area_not_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": True,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "SIXTH_SCHEDULE" in result["reasons"]

def test_insufficient_residency_not_eligible():
    result = check(SCHEME, {
        "religion": "hindu",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 3,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result["outcome"] == "NOT_ELIGIBLE"
    assert "RESIDENCY" in result["reasons"]

# --- source quote is present ---

def test_result_carries_a_source_quote():
    result = check(SCHEME, {
        "religion": "muslim",
        "origin_country": "pakistan",
        "entered_india_year": 2010,
        "years_in_india": 6,
        "inner_line_state": False,
        "sixth_schedule_area": False,
    })
    assert result.get("clauses") and result["clauses"][0]["quote"] and len(result["clauses"][0]["quote"]) > 10

# --- form spec ---

def test_form_spec_has_all_fields():
    spec = form_spec(SCHEME)
    field_names = {f["name"] for f in spec["fields"]}
    assert {"religion", "origin_country", "entered_india_year", "years_in_india",
            "inner_line_state", "sixth_schedule_area"} <= field_names

def test_religion_field_is_enum_with_six_covered_plus_others():
    spec = form_spec(SCHEME)
    religion = next(f for f in spec["fields"] if f["name"] == "religion")
    values = {o["value"] for o in religion["options"]}
    assert {"hindu", "sikh", "buddhist", "jain", "parsi", "christian", "muslim", "other"} <= values

def test_origin_country_enum_has_three_covered_countries():
    spec = form_spec(SCHEME)
    country = next(f for f in spec["fields"] if f["name"] == "origin_country")
    values = {o["value"] for o in country["options"]}
    assert {"pakistan", "bangladesh", "afghanistan"} <= values
