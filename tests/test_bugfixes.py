import json

import pytest
from fastapi.testclient import TestClient

from policy_wind_tunnel import settings
from policy_wind_tunnel.civic.research import SearchResult, lookup_representatives
from policy_wind_tunnel.contract.evaluator import evaluate
from policy_wind_tunnel.contract.gold import GOLD_CONTRACT_DATA, LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.service.app import create_app
from policy_wind_tunnel.simulation.whatif import dedupe_reasons

# ---------- 1. the default model ----------


def test_the_default_model_is_the_one_that_was_verified():
    assert settings.DEFAULT_MODEL == "gemini-2.5-flash"
    assert settings.model_name() == "gemini-2.5-flash"


def test_the_llm_client_uses_the_same_default():
    from policy_wind_tunnel.agents import llm

    assert llm.DEFAULT_MODEL == settings.DEFAULT_MODEL


def test_the_example_env_file_names_the_same_model():
    from pathlib import Path

    text = (Path(__file__).parent.parent / ".env.example").read_text()
    assert f"PWT_MODEL={settings.DEFAULT_MODEL}" in text


# ---------- 2. a contract from the model with different field names ----------


def rename_names(source, renames):
    import ast

    tree = ast.parse(source.strip(), mode="eval")
    spans = sorted(
        ((n.col_offset, n.end_col_offset, renames[n.id]) for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id in renames),
        reverse=True,
    )
    text = source.strip()
    for a, b, new in spans:
        text = text[:a] + new + text[b:]
    return text


def foreign_contract():
    renames = {"age": "applicant_age", "monthly_income": "verified_monthly_income"}
    data = json.loads(json.dumps(GOLD_CONTRACT_DATA))
    for f in data["fields"]:
        f["name"] = renames.get(f["name"], f["name"])
    for d in data["derived"]:
        d["expr"] = rename_names(d["expr"], renames)
    for stage in data["stages"]:
        for rule in stage["rules"]:
            rule["when"] = rename_names(rule["when"], renames)
    Contract.model_validate(data)
    return data


@pytest.fixture()
def client():
    return TestClient(create_app(llm=None))


def test_run_with_a_contract_that_does_not_match_the_software_is_a_clean_error_not_a_500(client):
    response = client.post("/api/run", json={"target": "reference", "contract": foreign_contract()})
    assert response.status_code == 422
    detail = response.json()["detail"].lower()
    assert "field" in detail and "software" in detail


def test_whatif_with_a_contract_that_does_not_match_is_a_clean_error(client):
    scenario = client.get("/api/demo").json()["scenarios"][0]["id"]
    response = client.post("/api/whatif", json={"scenario": scenario, "contract": foreign_contract(), "population": 100})
    assert response.status_code == 422


def test_the_error_names_the_fields_the_software_expects_and_the_ones_it_got(client):
    detail = client.post("/api/run", json={"target": "reference", "contract": foreign_contract()}).json()["detail"]
    assert "applicant_age" in detail and "age" in detail


def test_a_matching_contract_still_runs(client):
    assert client.post("/api/run", json={"target": "reference", "use_gold": True}).status_code == 200


# ---------- 3. duplicate rejection reasons ----------


def test_dedupe_keeps_first_occurrence_order():
    assert dedupe_reasons(["AGE", "INCOME", "INCOME", "CAP", "AGE"]) == ["AGE", "INCOME", "CAP"]
    assert dedupe_reasons([]) == []


def test_two_rules_with_the_same_reason_report_it_once():
    data = json.loads(json.dumps(GOLD_CONTRACT_DATA))
    rules = data["stages"][1]["rules"]
    extra = dict(rules[1], id="R3a_dup")
    rules.insert(2, extra)
    contract = Contract.model_validate(data)
    inputs = {
        "age": 35, "employment": "salaried", "monthly_income": 20000, "business_vintage_months": None, "credit_score": 750,
        "existing_obligations": 0, "proposed_emi": 0, "loan_amount": 1000, "documents": ["id_proof", "address_proof", "income_proof"],
        "relationship_months": 0, "has_delinquency": False,
    }
    assert evaluate(contract, inputs)["reasons"] == ["INCOME"]


def test_the_gold_contract_is_unchanged_by_deduplication():
    inputs = {
        "age": 19, "employment": "salaried", "monthly_income": 20000, "business_vintage_months": None, "credit_score": 750,
        "existing_obligations": 0, "proposed_emi": 0, "loan_amount": 1000, "documents": ["id_proof", "address_proof", "income_proof"],
        "relationship_months": 0, "has_delinquency": False,
    }
    assert evaluate(LENDING_CONTRACT, inputs) == {"outcome": "REJECT", "reasons": ["AGE", "INCOME"]}


# ---------- live lookup: handles, role/party/terms, left-out names, empty results ----------

NOTES = """Intro text.

**1. Seah Kian Peng**
*   **Role:** Speaker of Parliament, Member of Parliament
*   **Body:** Parliament of Singapore
*   **Party:** People's Action Party (PAP)
*   **Terms Served:**
    *   Member of Parliament from 2006 to 2025.
*   **Facts:**
    *   Elected as Speaker on August 2, 2023.
*   **Official Social Media:** Not listed on official pages.

**2. Goh Pei Ming**
*   **Role:** Senior Minister of State
*   **Party:** People's Action Party (PAP)
*   **Facts:**
    *   Served in the Armed Forces until March 31, 2025.
*   **Official Social Media:** Goh Pei Ming (Facebook)
"""


def result():
    cut = NOTES.index("**2. Goh")
    return SearchResult(
        NOTES,
        [{"url": "https://r/1", "title": "parliament.gov.sg"}, {"url": "https://r/2", "title": "wikipedia.org"}],
        supports=[{"start": 0, "end": cut, "indices": [0]}, {"start": cut, "end": len(NOTES), "indices": [1]}],
    )


class Searcher:
    def __init__(self, people, res=None):
        self.people, self.res = people, res or result()

    def search(self, prompt):
        return self.res

    def structure(self, prompt):
        return json.dumps({"representatives": self.people})


def model_person(name, **overrides):
    base = {"name": name, "role": "Made-up role", "body": "Made-up body", "constituency": "C", "party": "Made-up party", "terms": 9, "facts": [], "handles": {}}
    base.update(overrides)
    return base


def run(people, res=None):
    return lookup_representatives(Searcher(people, res), "Singapore", "C", "2026-10-14")


def test_handles_are_dropped_when_the_notes_say_none_are_listed():
    person = run([model_person("Seah Kian Peng", handles={"facebook": "SeahKianPeng", "instagram": "seahkianpeng"})])["representatives"][0]
    assert person["handles"] == {}


def test_handles_are_kept_when_the_notes_list_the_account():
    person = run([model_person("Goh Pei Ming", handles={"facebook": "GohPeiMing.Official"})])["representatives"][0]
    assert person["handles"] == {"facebook": "GohPeiMing.Official"}


def test_a_handle_for_a_platform_the_notes_do_not_mention_is_dropped():
    person = run([model_person("Goh Pei Ming", handles={"facebook": "GohPeiMing.Official", "instagram": "goh.pei.ming"})])["representatives"][0]
    assert person["handles"] == {"facebook": "GohPeiMing.Official"}


def test_role_and_party_come_from_the_notes_not_from_the_model():
    person = run([model_person("Seah Kian Peng")])["representatives"][0]
    assert person["role"] == "Speaker of Parliament, Member of Parliament"
    assert person["party"] == "People's Action Party (PAP)" and person["body"] == "Parliament of Singapore"


def test_terms_are_not_taken_from_the_model():
    person = run([model_person("Seah Kian Peng", terms=9)])["representatives"][0]
    assert person["terms"] is None


def test_a_person_whose_notes_have_no_role_line_falls_back_to_a_neutral_label():
    notes = NOTES.replace("*   **Role:** Senior Minister of State\n", "")
    res = result()
    res.text = notes
    person = run([model_person("Goh Pei Ming")], res)["representatives"][0]
    assert person["role"] == "Representative"


def test_left_out_lists_only_names_that_appear_in_the_notes():
    out = run([model_person("Seah Kian Peng"), model_person("Wholly Invented Person")])
    assert out["left_out"] == []
    assert out["dropped"] >= 1


def test_a_real_person_with_no_usable_source_is_listed_as_left_out():
    res = result()
    res.sources = [{"url": "https://r/1", "title": "facebook.com"}, {"url": "https://r/2", "title": "wikipedia.org"}]
    out = run([model_person("Seah Kian Peng"), model_person("Goh Pei Ming")], res)
    assert [p["name"] for p in out["representatives"]] == ["Goh Pei Ming"]
    assert out["left_out"] == ["Seah Kian Peng"]


def test_an_empty_lookup_is_not_cached():
    calls = []

    class Counting(Searcher):
        def search(self, prompt):
            calls.append(prompt)
            return SearchResult("Nobody found.", [{"url": "https://r/1", "title": "parliament.gov.sg"}])

        def structure(self, prompt):
            return json.dumps({"representatives": [], "bodies": []})

    client = TestClient(create_app(llm=object(), searcher=Counting([])))
    body = {"country": "sg", "place": "Nowhere Town"}
    client.post("/api/civic/leaders/lookup", json=body)
    first = len(calls)
    client.post("/api/civic/leaders/lookup", json=body)
    assert len(calls) == 2 * first


def test_a_non_empty_lookup_is_still_cached():
    calls = []

    class Counting(Searcher):
        def search(self, prompt):
            calls.append(prompt)
            return result()

    client = TestClient(create_app(llm=object(), searcher=Counting([model_person("Seah Kian Peng")])))
    body = {"country": "sg", "place": "Marine Parade GRC"}
    client.post("/api/civic/leaders/lookup", json=body)
    first = len(calls)
    client.post("/api/civic/leaders/lookup", json=body)
    assert len(calls) == first


# ---------- 8. tests never touch the real key ----------


def test_the_test_environment_has_no_credentials():
    assert settings.credential_mode() == "none"


def test_an_app_created_in_tests_does_not_pick_up_a_real_env_file():
    assert TestClient(create_app()).get("/api/health").json()["llm"] is False
