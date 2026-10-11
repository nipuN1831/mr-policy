import concurrent.futures
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from policy_wind_tunnel.adversary.mcdc import GeneratedCase
from policy_wind_tunnel.contract.evaluator import evaluate_traced
from policy_wind_tunnel.contract.models import Contract

Implementation = Callable[[dict[str, Any]], dict[str, Any]]
DEFAULT_TIMEOUT_SECONDS = 2.0
_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)


@dataclass
class Finding:
    kind: str
    inputs: dict[str, Any]
    expected: dict[str, Any]
    actual: dict[str, Any]
    fired_rules: list[str]
    clause: str
    source_quote: str
    rule_id: str
    case_kind: str
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _call(implementation: Implementation, inputs: dict[str, Any], timeout: float) -> tuple[str, dict[str, Any]]:
    future = _POOL.submit(implementation, dict(inputs))
    try:
        return "ok", future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        future.cancel()
        return "timeout", {"error": f"no answer within {timeout}s"}
    except Exception as error:  # noqa: BLE001 - the implementation under test may raise anything
        return "crash", {"error": f"{type(error).__name__}: {error}"}


def _normalise(result: Any) -> dict[str, Any] | None:
    if not isinstance(result, dict) or "outcome" not in result:
        return None
    reasons = result.get("reasons", [])
    if not isinstance(reasons, (list, tuple)):
        return None
    return {"outcome": result["outcome"], "reasons": list(reasons)}


def _rule_index(contract: Contract) -> tuple[dict[str, tuple[str, str]], dict[str, list[str]]]:
    lookup: dict[str, tuple[str, str]] = {}
    by_reason: dict[str, list[str]] = {}
    for _, rule in contract.all_rules():
        lookup[rule.id] = (rule.clause, rule.source_quote)
        if rule.reason:
            by_reason.setdefault(rule.reason, []).append(rule.id)
    return lookup, by_reason


def _blame(
    expected: dict[str, Any],
    actual: dict[str, Any],
    fired: list[str],
    lookup: dict[str, tuple[str, str]],
    by_reason: dict[str, list[str]],
) -> tuple[str, str, str]:
    differing = set(expected["reasons"]) ^ set(actual.get("reasons", []))
    order = {rule_id: position for position, rule_id in enumerate(lookup)}
    candidates = sorted((rid for reason in differing for rid in by_reason.get(reason, [])), key=order.get)
    pool = candidates or fired
    for rule_id in pool:
        clause, quote = lookup[rule_id]
        if quote:
            return rule_id, clause, quote
    return pool[0], lookup[pool[0]][0], lookup[pool[0]][1]


def run_suite(
    contract: Contract,
    cases: list[GeneratedCase],
    implementation: Implementation,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> list[Finding]:
    lookup, by_reason = _rule_index(contract)
    findings: list[Finding] = []
    for case in cases:
        expected, fired = evaluate_traced(contract, case.inputs)
        status, raw = _call(implementation, case.inputs, timeout_seconds)
        actual = _normalise(raw) if status == "ok" else raw
        if status == "ok" and actual == expected:
            continue
        kind = status if status != "ok" else "mismatch"
        rule_id, clause, quote = _blame(expected, actual or {}, fired, lookup, by_reason)
        findings.append(
            Finding(
                kind=kind,
                inputs=case.inputs,
                expected=expected,
                actual=actual if actual is not None else {"raw": repr(raw)},
                fired_rules=fired,
                clause=clause,
                source_quote=quote,
                rule_id=rule_id,
                case_kind=case.kind,
                note=case.note,
            )
        )
    return findings
