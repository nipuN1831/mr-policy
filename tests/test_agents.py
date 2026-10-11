import json
from pathlib import Path

import pytest

from policy_wind_tunnel.agents.approval import ApprovalError, decide_ambiguity
from policy_wind_tunnel.agents.critic import critique
from policy_wind_tunnel.agents.extractor import ExtractionError, extract_contract
from policy_wind_tunnel.contract.gold import GOLD_CONTRACT_DATA, LENDING_CONTRACT
from policy_wind_tunnel.contract.models import Contract

POLICY = (Path(__file__).parent.parent / "src/policy_wind_tunnel/benchmark/lending_policy.md").read_text()


class FakeLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts = []

    def generate_json(self, system, prompt, schema=None):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("unexpected extra LLM call")
        return self.responses.pop(0)


def gold_json(mutate=None):
    data = json.loads(json.dumps(GOLD_CONTRACT_DATA))
    if mutate:
        mutate(data)
    return json.dumps(data)


def test_clean_extraction_returns_the_contract_in_one_attempt():
    llm = FakeLLM(gold_json())
    result = extract_contract(POLICY, llm)
    assert result.contract == LENDING_CONTRACT
    assert result.attempts == 1 and result.errors == []


def test_invalid_json_is_repaired_using_the_error_message():
    llm = FakeLLM("not json at all", gold_json())
    result = extract_contract(POLICY, llm)
    assert result.attempts == 2
    assert "JSON" in llm.prompts[1] and "not json at all" in llm.prompts[1]


def test_schema_violation_is_fed_back_and_repaired():
    def break_rule(data):
        data["stages"][1]["rules"][0]["when"] = "agee < 21"

    llm = FakeLLM(gold_json(break_rule), gold_json())
    result = extract_contract(POLICY, llm)
    assert result.attempts == 2
    assert "agee" in llm.prompts[1]


def test_invented_source_quote_is_rejected_and_repaired():
    def invent(data):
        data["stages"][1]["rules"][0]["source_quote"] = "Applicants over 65 are always rejected."

    llm = FakeLLM(gold_json(invent), gold_json())
    result = extract_contract(POLICY, llm)
    assert result.attempts == 2
    assert "Applicants over 65" in llm.prompts[1]


def test_quote_matching_ignores_whitespace_differences():
    def reflow(data):
        rule = data["stages"][1]["rules"][2]
        rule["source_quote"] = rule["source_quote"].replace("\n", "  ")

    result = extract_contract(POLICY, FakeLLM(gold_json(reflow)))
    assert result.attempts == 1


def test_gives_up_after_the_repair_budget_with_every_error_reported():
    llm = FakeLLM("bad", "worse", "worst")
    with pytest.raises(ExtractionError) as error:
        extract_contract(POLICY, llm, max_repairs=2)
    assert len(error.value.errors) == 3
    assert llm.responses == []


def test_code_fences_around_json_are_tolerated():
    result = extract_contract(POLICY, FakeLLM("```json\n" + gold_json() + "\n```"))
    assert result.attempts == 1


def test_critic_finds_a_clause_no_rule_cites():
    data = json.loads(gold_json())
    data["stages"][1]["rules"] = [r for r in data["stages"][1]["rules"] if r["id"] != "R5_cap"]
    report = critique(POLICY, Contract.model_validate(data))
    assert report.uncited_clauses == ["L5"]


def test_critic_is_clean_on_the_gold_contract():
    report = critique(POLICY, LENDING_CONTRACT)
    assert report.uncited_clauses == []
    assert report.uncovered_input is None
    assert report.unreachable_rules == []


def test_critic_reports_an_input_no_rule_decides():
    data = json.loads(gold_json())
    data["stages"][2]["rules"] = data["stages"][2]["rules"][:-1]
    report = critique(POLICY, Contract.model_validate(data))
    assert report.uncovered_input is not None


def test_llm_critic_adds_proposed_ambiguities_and_ignores_garbage():
    suggestion = json.dumps(
        {
            "ambiguities": [
                {"clause": "L1", "question": "Is age measured in whole years?", "resolution": "Assume whole years."}
            ]
        }
    )
    report = critique(POLICY, LENDING_CONTRACT, llm=FakeLLM(suggestion))
    assert report.proposed[0].status == "proposed" and report.proposed[0].clause == "L1"
    assert critique(POLICY, LENDING_CONTRACT, llm=FakeLLM("garbage")).proposed == []


def test_approval_changes_status_and_records_the_resolution():
    data = json.loads(gold_json())
    data["ambiguities"].append(
        {"id": "A9", "clause": "L1", "question": "q", "resolution": "r", "status": "proposed"}
    )
    contract = Contract.model_validate(data)
    updated = decide_ambiguity(contract, "A9", "approved", resolution="Whole years only.")
    item = next(a for a in updated.ambiguities if a.id == "A9")
    assert item.status == "approved" and item.resolution == "Whole years only."
    assert next(a for a in contract.ambiguities if a.id == "A9").status == "proposed"


def test_approval_rejects_unknown_ids_and_bad_statuses():
    with pytest.raises(ApprovalError):
        decide_ambiguity(LENDING_CONTRACT, "A99", "approved")
    with pytest.raises(ApprovalError):
        decide_ambiguity(LENDING_CONTRACT, "A1", "maybe")
