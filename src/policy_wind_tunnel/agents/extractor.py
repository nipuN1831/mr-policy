import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from policy_wind_tunnel.agents.llm import LLM
from policy_wind_tunnel.contract.models import Contract

SYSTEM = """You turn a written business policy into a machine-checkable policy contract.
Return ONE JSON object and nothing else. It must follow this structure:
- name, description, outcomes (list of outcome labels)
- fields: [{name, kind: int|bool|enum|set|str, nullable, min, max, values, typical}]
- derived: [{name, expr, clause, source_quote}] computed in order, each may use earlier names
- stages: [{name, mode: first_match|collect, rules: [{id, clause, source_quote, when, outcome, reason}]}]
  Stages run in order. The first stage that has a firing rule decides the outcome.
  In a collect stage every firing rule contributes its reason; in first_match only the first firing rule counts.
- ambiguities: [{id, clause, question, resolution, status: "proposed"}] for anything the policy leaves unclear
Expressions use only: and, or, not, + - *, comparisons, `is None`, `in`, tuples, literals, `x if c else y`, field and derived names.
No function calls, no division. Use integers only (percent checks as `a * 100 > 45 * b`).
Every rule needs the policy clause id it comes from and a source_quote copied VERBATIM from the policy text.
Do not invent rules that the policy does not state. If something is unclear, add an ambiguity instead of guessing silently."""

FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class ExtractionError(Exception):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors[-1:]))
        self.errors = errors


@dataclass
class ExtractionResult:
    contract: Contract
    attempts: int
    errors: list[str] = field(default_factory=list)


def _squash(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _quote_problems(contract: Contract, policy_text: str) -> list[str]:
    haystack = _squash(policy_text)
    quotes = [(f"rule {r.id}", r.source_quote) for _, r in contract.all_rules()]
    quotes += [(f"derived {d.name}", d.source_quote) for d in contract.derived]
    return [
        f"{owner} quotes text that is not in the policy: {quote!r}"
        for owner, quote in quotes
        if quote and _squash(quote) not in haystack
    ]


def _parse(raw: str) -> Contract:
    text = FENCE.sub("", raw.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"the reply was not valid JSON: {error}") from error
    try:
        return Contract.model_validate(data)
    except ValidationError as error:
        details = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in error.errors()[:8])
        raise ValueError(f"the contract failed validation: {details}") from error


def _prompt(policy_text: str, previous: str, problem: str) -> str:
    if not problem:
        return f"Policy text:\n\n{policy_text}\n\nReturn the contract JSON."
    return (
        f"Policy text:\n\n{policy_text}\n\nYour previous reply was rejected.\n"
        f"Problem: {problem}\nPrevious reply:\n{previous[:6000]}\n\nReturn a corrected contract JSON."
    )


def extract_contract(policy_text: str, llm: LLM, max_repairs: int = 3) -> ExtractionResult:
    errors: list[str] = []
    previous, problem = "", ""
    schema = Contract.model_json_schema()
    for attempt in range(1, max_repairs + 2):
        raw = llm.generate_json(SYSTEM, _prompt(policy_text, previous, problem), schema)
        try:
            contract = _parse(raw)
            quote_problems = _quote_problems(contract, policy_text)
            if quote_problems:
                raise ValueError("; ".join(quote_problems[:5]))
            return ExtractionResult(contract, attempt, errors)
        except ValueError as error:
            problem, previous = str(error), raw
            errors.append(problem)
    raise ExtractionError(errors)
