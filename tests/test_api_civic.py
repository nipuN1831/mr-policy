import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.service.app import create_app

SILVER_INPUTS = dict(
    citizen=True, age=70, self_employed=False, cpf_by_55=100000, trade_income_45_54=None,
    housing="hdb_4", owns_big_property=False, pchi=2400,
)


@pytest.fixture()
def client():
    return TestClient(create_app(llm=None))


def test_countries_lists_five_with_status(client):
    countries = client.get("/api/civic/countries").json()
    assert {"in", "sg", "au", "ph", "id"} <= {c["code"] for c in countries}
    assert all(c["status"] in ("verified", "partial") for c in countries)


def test_country_pack_is_served_with_schemes_flagged(client):
    pack = client.get("/api/civic/countries/sg").json()
    assert pack["code"] == "sg" and pack["representatives"]
    flags = {s["id"]: s["self_check"] for s in pack["schemes"]}
    assert flags["sg_silver_support"] is True


def test_unknown_country_is_404(client):
    assert client.get("/api/civic/countries/zz").status_code == 404


def test_problem_finder_returns_matching_problems(client):
    body = client.get("/api/civic/countries/in/problems", params={"text": "bank refused a refund"}).json()
    assert body["matches"] and body["matches"][0]["id"] == "bank_issue"
    assert client.get("/api/civic/countries/in/problems", params={"text": "zzzz"}).json()["matches"] == []


def test_representatives_endpoint_returns_real_mps(client):
    body = client.get("/api/civic/countries/in/representatives", params={"constituency": "Varanasi"}).json()
    assert body["representatives"]
    assert body["demo"] is False
    assert all(not r["fictional"] for r in body["representatives"])


def test_representatives_endpoint_demo_flag_true_when_fictional(client):
    body = client.get("/api/civic/countries/sg/representatives", params={"constituency": "Tanjong Pagar"}).json()
    assert "notice" in body and "demo" in body


def test_scheme_list_and_form(client):
    schemes = client.get("/api/civic/schemes").json()
    assert any(s["id"] == "sg_silver_support" and s["self_check"] for s in schemes)
    form = client.get("/api/civic/schemes/sg_silver_support/form").json()
    assert form["fields"] and form["policy_text"]


def test_check_returns_a_decision_with_the_clause(client):
    body = client.post("/api/civic/schemes/sg_silver_support/check", json={"inputs": SILVER_INPUTS}).json()
    assert body["outcome"] == "NOT_ELIGIBLE" and body["reasons"] == ["INCOME"]
    assert "2,300" in body["clauses"][0]["quote"]


def test_change_returns_the_smallest_flip(client):
    body = client.post("/api/civic/schemes/sg_silver_support/change", json={"inputs": SILVER_INPUTS}).json()
    assert body["alternatives"][0]["changes"] == [{"field": "pchi", "from": 2400, "to": 2300}]
    assert body["alternatives"][0]["outcome"] == "PAY_325"


def test_change_accepts_a_target_and_locks(client):
    body = client.post(
        "/api/civic/schemes/sg_silver_support/change",
        json={"inputs": {**SILVER_INPUTS, "pchi": 2000}, "targets": ["PAY_650"], "lock": ["housing"]},
    ).json()
    assert body["alternatives"][0]["changes"] == [{"field": "pchi", "from": 2000, "to": 1500}]


def test_bad_inputs_and_unknown_schemes_are_clean_errors(client):
    assert client.post("/api/civic/schemes/sg_silver_support/check", json={"inputs": {**SILVER_INPUTS, "housing": "castle"}}).status_code == 422
    assert client.post("/api/civic/schemes/nope/check", json={"inputs": {}}).status_code == 404
    assert client.get("/api/civic/schemes/nope/form").status_code == 404
    bad_target = client.post("/api/civic/schemes/sg_silver_support/change", json={"inputs": SILVER_INPUTS, "targets": ["NOPE"]})
    assert bad_target.status_code == 422


def test_scheme_without_a_contract_explains_why(client):
    schemes = client.get("/api/civic/countries/ph").json()["schemes"]
    no_contract = [s for s in schemes if not s["self_check"]]
    assert no_contract
    response = client.post(f"/api/civic/schemes/{no_contract[0]['id']}/check", json={"inputs": {}})
    assert response.status_code == 422 and "caseworker" in response.json()["detail"].lower()


def test_nothing_the_citizen_enters_is_kept(client):
    client.post("/api/civic/schemes/sg_silver_support/check", json={"inputs": SILVER_INPUTS})
    again = client.get("/api/civic/schemes/sg_silver_support/form").text
    assert "2400" not in again


def test_citizen_page_is_served(client):
    page = client.get("/citizen")
    assert page.status_code == 200 and "Do I qualify?" in page.text
    assert "information only" in page.text.lower()


def test_upcoming_policies_endpoint_returns_list(client):
    body = client.get("/api/civic/countries/in/policies/upcoming").json()
    assert "policies" in body and len(body["policies"]) >= 3
    policy = body["policies"][0]
    assert {"id", "title", "summary", "status", "projected_impacts"} <= policy.keys()


def test_upcoming_policies_filter_by_status(client):
    body = client.get("/api/civic/countries/in/policies/upcoming", params={"status": "proposed"}).json()
    assert all(p["status"] == "proposed" for p in body["policies"])
    assert body["policies"]


def test_upcoming_policies_unknown_status_returns_empty(client):
    body = client.get("/api/civic/countries/in/policies/upcoming", params={"status": "nonexistent"}).json()
    assert body["policies"] == []


def test_find_representatives_fuzzy_match(client):
    body = client.get("/api/civic/countries/in/representatives", params={"constituency": "Gautam Buddha Nagar"}).json()
    assert body["representatives"]


def test_find_representatives_by_name(client):
    body = client.get("/api/civic/countries/in/representatives", params={"constituency": "Narendra Modi"}).json()
    assert body["representatives"]
    assert any("Modi" in r["name"] for r in body["representatives"])


def test_find_representatives_partial_name(client):
    body = client.get("/api/civic/countries/in/representatives", params={"constituency": "Rahul Gandhi"}).json()
    assert body["representatives"]
    assert any("Gandhi" in r["name"] for r in body["representatives"])


def test_find_representatives_empty_for_unknown(client):
    body = client.get("/api/civic/countries/in/representatives", params={"constituency": "Nowhere Constituency"}).json()
    assert body["representatives"] == []
