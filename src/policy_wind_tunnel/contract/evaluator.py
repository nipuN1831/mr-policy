from typing import Any

from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.expr import ExprError
from policy_wind_tunnel.contract.models import Contract, FieldSpec, Stage


class ContractError(Exception):
    pass


def _coerce_value(spec: FieldSpec, value: Any) -> Any:
    if spec.kind == "int":
        if type(value) is not int:
            raise ContractError(f"{spec.name} must be an integer, got {value!r}")
        return value
    if spec.kind == "bool":
        if type(value) is not bool:
            raise ContractError(f"{spec.name} must be a boolean, got {value!r}")
        return value
    if spec.kind == "str":
        if not isinstance(value, str):
            raise ContractError(f"{spec.name} must be a string, got {value!r}")
        return value
    if spec.kind == "enum":
        if value not in spec.values:
            raise ContractError(f"{spec.name} must be one of {spec.values}, got {value!r}")
        return value
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise ContractError(f"{spec.name} must be a collection, got {value!r}")
    items = frozenset(value)
    unexpected = items - set(spec.values)
    if unexpected:
        raise ContractError(f"{spec.name} has unexpected members {sorted(map(str, unexpected))}")
    return items


def coerce_inputs(contract: Contract, inputs: dict[str, Any]) -> dict[str, Any]:
    specs = contract.field_map()
    unknown = set(inputs) - set(specs)
    if unknown:
        raise ContractError(f"unknown input fields {sorted(unknown)}")
    coerced: dict[str, Any] = {}
    for name, spec in specs.items():
        if inputs.get(name) is None:
            if not spec.nullable:
                raise ContractError(f"{name} is required")
            coerced[name] = None
        else:
            coerced[name] = _coerce_value(spec, inputs[name])
    return coerced


def _compute_derived(contract: Contract, env: dict[str, Any]) -> None:
    for derived in contract.derived:
        try:
            env[derived.name] = expr.evaluate(derived.expr, env)
        except ExprError as error:
            raise ContractError(f"derived {derived.name}: {error}") from error


def _fires(rule_when: str, rule_id: str, env: dict[str, Any]) -> bool:
    try:
        result = expr.evaluate(rule_when, env)
    except ExprError as error:
        raise ContractError(f"rule {rule_id}: {error}") from error
    if not isinstance(result, bool):
        raise ContractError(f"rule {rule_id} did not produce a boolean")
    return result


def _run_stage(stage: Stage, env: dict[str, Any]) -> tuple[str, list[str], list[str]] | None:
    fired = []
    for rule in stage.rules:
        if _fires(rule.when, rule.id, env):
            fired.append(rule)
            if stage.mode == "first_match":
                break
    if not fired:
        return None
    reasons = [rule.reason for rule in fired if rule.reason]
    return fired[0].outcome, reasons, [rule.id for rule in fired]


def evaluate_traced(contract: Contract, inputs: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    env = coerce_inputs(contract, inputs)
    _compute_derived(contract, env)
    for stage in contract.stages:
        decided = _run_stage(stage, env)
        if decided:
            outcome, reasons, fired = decided
            return {"outcome": outcome, "reasons": reasons}, fired
    raise ContractError("no rule decided the outcome")


def evaluate(contract: Contract, inputs: dict[str, Any]) -> dict[str, Any]:
    return evaluate_traced(contract, inputs)[0]
