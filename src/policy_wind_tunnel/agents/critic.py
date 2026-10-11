import json
import re
from dataclasses import dataclass, field

from policy_wind_tunnel.adversary.symbolic import SymbolicContract, Unsupported
from policy_wind_tunnel.agents.llm import LLM
from policy_wind_tunnel.contract.models import Ambiguity, Contract

CLAUSE_HEADING = re.compile(r"^##\s+(L\d+)\b", re.MULTILINE)

SYSTEM = """You review a policy contract for gaps. Reply with JSON: {"ambiguities": [{"clause", "question", "resolution"}]}.
Only list real ambiguities: places where two reasonable readings of the policy text would give different outcomes.
Give the reading you think is most likely as the resolution. Do not repeat items already listed."""


@dataclass
class CritiqueReport:
    uncited_clauses: list[str] = field(default_factory=list)
    unreachable_rules: list[str] = field(default_factory=list)
    uncovered_input: dict | None = None
    proposed: list[Ambiguity] = field(default_factory=list)
    symbolic_supported: bool = True


def _clauses_in(policy_text: str) -> list[str]:
    return CLAUSE_HEADING.findall(policy_text)


def _structural(policy_text: str, contract: Contract, report: CritiqueReport) -> None:
    cited = {rule.clause for _, rule in contract.all_rules()} | {d.clause for d in contract.derived}
    report.uncited_clauses = [c for c in _clauses_in(policy_text) if c not in cited]


def _symbolic(contract: Contract, report: CritiqueReport) -> None:
    try:
        symbolic = SymbolicContract(contract)
    except Unsupported:
        report.symbolic_supported = False
        return
    report.unreachable_rules = [r for r in symbolic.rule_ids() if not symbolic.can_fire(r)]
    report.uncovered_input = symbolic.find_uncovered_input()


def _llm_ambiguities(policy_text: str, contract: Contract, llm: LLM) -> list[Ambiguity]:
    listed = [f"{a.clause}: {a.question}" for a in contract.ambiguities]
    prompt = f"Policy:\n{policy_text}\n\nContract:\n{contract.model_dump_json()}\n\nAlready listed: {listed}"
    try:
        data = json.loads(llm.generate_json(SYSTEM, prompt))
        items = data["ambiguities"]
        known = {a.id for a in contract.ambiguities}
        proposed = []
        for index, item in enumerate(items, start=1):
            proposed.append(
                Ambiguity(
                    id=f"P{index}",
                    clause=str(item["clause"]),
                    question=str(item["question"]),
                    resolution=str(item["resolution"]),
                    status="proposed",
                )
            )
        return [p for p in proposed if p.id not in known]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return []


def critique(policy_text: str, contract: Contract, llm: LLM | None = None) -> CritiqueReport:
    report = CritiqueReport()
    _structural(policy_text, contract, report)
    _symbolic(contract, report)
    if llm is not None:
        report.proposed = _llm_ambiguities(policy_text, contract, llm)
    return report
