import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.contract.gold import GOLD_CONTRACT_DATA
from policy_wind_tunnel.service.app import create_app


@pytest.fixture()
def client():
    return TestClient(create_app(llm=None))


def test_demo_lists_the_preset_scenarios(client):
    scenarios = client.get("/api/demo").json()["scenarios"]
    assert len(scenarios) >= 5
    assert all({"id", "title", "description", "changes"} <= s.keys() for s in scenarios)


def test_whatif_with_a_preset_reports_flips_and_code_impact(client):
    scenario = client.get("/api/demo").json()["scenarios"][0]
    body = client.post("/api/whatif", json={"scenario": scenario["id"], "population": 2000, "use_gold": True}).json()
    assert body["simulation"]["population"] == 2000
    assert body["simulation"]["flipped"] > 0
    assert body["simulation"]["examples"]
    assert body["code_impact"]["failing_cases"] > 0
    assert body["health"] == {"unreachable_rules": [], "uncovered_input": None}
    assert body["scenario"]["id"] == scenario["id"]


def test_whatif_with_custom_changes(client):
    changes = [{"target": "R5_cap", "expr": "loan_amount > 10 * monthly_income", "note": "Cap at 10x income"}]
    body = client.post("/api/whatif", json={"changes": changes, "population": 1500, "use_gold": True}).json()
    assert body["simulation"]["flipped"] > 0
    assert body["simulation"]["reasons_gained"].get("CAP", 0) > 0


def test_whatif_rejects_bad_requests(client):
    assert client.post("/api/whatif", json={"scenario": "nope", "use_gold": True}).status_code == 404
    assert client.post("/api/whatif", json={"use_gold": True}).status_code == 422
    bad = client.post("/api/whatif", json={"changes": [{"target": "R1_age", "expr": "zzz > 1"}], "use_gold": True})
    assert bad.status_code == 422
    assert client.post("/api/whatif", json={"scenario": "x", "population": 10**7, "use_gold": True}).status_code == 422


def test_whatif_accepts_a_supplied_contract(client):
    scenario = client.get("/api/demo").json()["scenarios"][0]
    body = client.post(
        "/api/whatif", json={"scenario": scenario["id"], "population": 500, "contract": GOLD_CONTRACT_DATA}
    ).json()
    assert body["simulation"]["population"] == 500
