import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.contract.gold import LENDING_CONTRACT
from policy_wind_tunnel.service.app import create_app
from policy_wind_tunnel.simulation.levers import levers


@pytest.fixture()
def client():
    return TestClient(create_app(llm=None))


def by_field(report):
    return {item["field"]: item for item in report["levers"]}


def test_every_field_is_listed_once():
    report = levers(LENDING_CONTRACT)
    assert sorted(by_field(report)) == sorted(f.name for f in LENDING_CONTRACT.fields)
    assert len(report["levers"]) == len(LENDING_CONTRACT.fields)


def test_a_field_lists_the_rules_that_read_it_with_their_source_clause():
    age = by_field(levers(LENDING_CONTRACT))["age"]
    assert age["rules"] and all({"id", "clause", "outcome"} <= r.keys() for r in age["rules"])
    assert "AGE" in age["reasons"]


def test_a_field_used_only_through_a_derived_value_still_reaches_the_rules():
    rule_ids = {r["id"] for r in by_field(levers(LENDING_CONTRACT))["existing_obligations"]["rules"]}
    assert rule_ids


def test_outcomes_a_field_can_cause_are_reported():
    income = by_field(levers(LENDING_CONTRACT))["monthly_income"]
    assert set(income["outcomes"]) <= set(LENDING_CONTRACT.outcomes) and income["outcomes"]


def test_an_unused_field_has_no_rules():
    data = LENDING_CONTRACT.model_dump()
    data["fields"].append({"name": "unused_field", "kind": "int"})
    from policy_wind_tunnel.contract.models import Contract

    item = by_field(levers(Contract.model_validate(data)))["unused_field"]
    assert item["rules"] == [] and item["outcomes"] == []


def test_fields_are_ordered_by_how_many_rules_they_touch():
    counts = [len(i["rules"]) for i in levers(LENDING_CONTRACT)["levers"]]
    assert counts == sorted(counts, reverse=True)


def test_the_levers_endpoint_serves_the_report(client):
    body = client.post("/api/levers", json={"use_gold": True}).json()
    assert {i["field"] for i in body["levers"]} >= {"age", "monthly_income"}
    assert "not a causal" in body["note"].lower()


def test_the_levers_endpoint_rejects_an_invalid_contract(client):
    assert client.post("/api/levers", json={"contract": {"name": "x"}}).status_code == 422
