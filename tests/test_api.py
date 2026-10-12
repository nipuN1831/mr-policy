import json

import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel.contract.gold import GOLD_CONTRACT_DATA
from policy_wind_tunnel.service.app import create_app


class StubLLM:
    def generate_json(self, system, prompt, schema=None):
        return json.dumps(GOLD_CONTRACT_DATA)


@pytest.fixture()
def client():
    return TestClient(create_app(llm=StubLLM()))


@pytest.fixture()
def offline_client():
    return TestClient(create_app(llm=None))


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "llm": True}


def test_health_reports_missing_llm(offline_client):
    assert offline_client.get("/api/health").json()["llm"] is False


def test_demo_lists_policy_and_targets(client):
    data = client.get("/api/demo").json()
    assert "Fictional Retail Lending" in data["policy_text"]
    ids = [t["id"] for t in data["targets"]]
    assert ids[0] == "reference" and len(ids) == 11
    assert all(t["clause"] for t in data["targets"][1:])


def test_extract_with_llm_returns_contract_and_critique(client):
    demo = client.get("/api/demo").json()
    body = client.post("/api/extract", json={"policy_text": demo["policy_text"]}).json()
    assert body["source"] == "llm" and body["attempts"] == 1
    assert body["contract"]["name"] == GOLD_CONTRACT_DATA["name"]
    assert body["critique"]["uncited_clauses"] == []


def test_extract_without_llm_requires_explicit_gold(offline_client):
    demo = offline_client.get("/api/demo").json()
    refused = offline_client.post("/api/extract", json={"policy_text": demo["policy_text"]})
    assert refused.status_code == 503
    gold = offline_client.post("/api/extract", json={"policy_text": demo["policy_text"], "use_gold": True}).json()
    assert gold["source"] == "gold"


def test_extract_reports_failure_after_repairs():
    class Bad:
        def generate_json(self, system, prompt, schema=None):
            return "nope"

    response = TestClient(create_app(llm=Bad())).post("/api/extract", json={"policy_text": "x"})
    assert response.status_code == 422 and len(response.json()["detail"]["errors"]) == 4


def test_run_against_correct_engine_finds_nothing(client):
    body = client.post("/api/run", json={"target": "reference", "use_gold": True}).json()
    assert body["cases"] > 40 and body["findings"] == 0 and body["clusters"] == []


def test_run_against_a_mutant_returns_evidence_and_verified_regression(client):
    body = client.post("/api/run", json={"target": "M03_income_strict", "use_gold": True}).json()
    assert body["findings"] > 0
    cluster = body["clusters"][0]
    assert cluster["clause"] == "L3" and cluster["verdict"] == "defect"
    rep = cluster["representative"]
    assert rep["inputs"]["monthly_income"] == 25000
    assert rep["expected"]["outcome"] != rep["actual"]["outcome"]
    assert "25,000" in rep["source_quote"]
    assert "def test_" in body["regression"]["source"]
    assert body["regression"]["failing_on_buggy"] == body["regression"]["tests"] > 0
    assert body["regression"]["passing_on_fixed"] == body["regression"]["tests"]


def test_run_with_unknown_target_is_a_404(client):
    assert client.post("/api/run", json={"target": "nope", "use_gold": True}).status_code == 404


def test_run_with_a_supplied_contract_and_unapproved_ambiguity(client):
    contract = json.loads(json.dumps(GOLD_CONTRACT_DATA))
    for item in contract["ambiguities"]:
        if item["clause"] == "L4":
            item["status"] = "proposed"
    body = client.post("/api/run", json={"target": "M06_dti_strict", "contract": contract}).json()
    assert body["clusters"] and all(c["verdict"] == "needs_clarification" for c in body["clusters"])
    assert body["regression"]["tests"] == 0


def test_run_rejects_an_invalid_contract(client):
    response = client.post("/api/run", json={"target": "reference", "contract": {"name": "x"}})
    assert response.status_code == 422


def test_approve_flips_the_ambiguity_status(client):
    contract = json.loads(json.dumps(GOLD_CONTRACT_DATA))
    contract["ambiguities"][0]["status"] = "proposed"
    body = client.post(
        "/api/approve",
        json={"contract": contract, "ambiguity_id": "A1", "status": "approved", "resolution": "Exactly 45% passes."},
    ).json()
    item = next(a for a in body["contract"]["ambiguities"] if a["id"] == "A1")
    assert item["status"] == "approved" and item["resolution"] == "Exactly 45% passes."


def test_approve_unknown_ambiguity_is_a_404(client):
    response = client.post(
        "/api/approve", json={"contract": GOLD_CONTRACT_DATA, "ambiguity_id": "ZZ", "status": "approved"}
    )
    assert response.status_code == 404


def test_benchmark_reports_the_headline_numbers(client):
    body = client.get("/api/benchmark").json()
    assert body["recall"] == 1.0 and body["precision"] == 1.0
    assert body["baseline_recall"] == 0.4
    assert len(body["rows"]) == 10


def test_landing_page_offers_both_paths(client):
    page = client.get("/")
    assert page.status_code == 200 and "Policy Wind Tunnel" in page.text
    assert 'href="/citizen"' in page.text and 'href="/officials"' in page.text


def test_officials_page_is_served_with_its_four_tabs(client):
    page = client.get("/officials")
    assert page.status_code == 200
    for label in ("Policy", "What if we change it?", "Test the software", "How well does it work?"):
        assert label in page.text


def test_shared_stylesheet_is_served(client):
    css = client.get("/static/app.css")
    assert css.status_code == 200 and "--brand" in css.text
    assert client.get("/static/does-not-exist.css").status_code == 404
