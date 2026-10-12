from dataclasses import dataclass, field
from itertools import combinations
from typing import Any

import z3

from policy_wind_tunnel.adversary.symbolic import SymbolicContract
from policy_wind_tunnel.civic.eligibility import SchemeSpec
from policy_wind_tunnel.contract.evaluator import coerce_inputs, evaluate
from policy_wind_tunnel.contract.models import FieldSpec

MAX_FIELDS_CHANGED = 3


@dataclass
class Alternative:
    changes: list[dict[str, Any]]
    outcome: str
    outcome_label: str
    cost: int

    @property
    def summary(self) -> str:
        parts = [f"{c['field']}: {c['from']} to {c['to']}" for c in self.changes]
        return "; ".join(parts) + f" gives {self.outcome_label}"


@dataclass
class Counterfactual:
    current_outcome: str
    already_met: bool
    alternatives: list[Alternative] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "current_outcome": self.current_outcome,
            "already_met": self.already_met,
            "blocked_by": self.blocked_by,
            "alternatives": [
                {"changes": a.changes, "outcome": a.outcome, "outcome_label": a.outcome_label, "cost": a.cost, "summary": a.summary}
                for a in self.alternatives
            ],
        }


def _field_vars(sym: SymbolicContract, name: str) -> list[Any]:
    return sym.vars[name].all_vars()


def _distance_terms(sym: SymbolicContract, name: str, spec: FieldSpec, current: dict[str, Any]) -> Any:
    fv = sym.vars[name]
    if spec.kind == "int" and fv.isnone is None:
        return z3.If(fv.val >= current[name], fv.val - current[name], current[name] - fv.val)
    return z3.IntVal(0)


def _solve(sym: SymbolicContract, spec: SchemeSpec, current: dict[str, Any], free: list[str], targets: list[str]):
    opt = z3.Optimize()
    opt.add(sym.domain)
    opt.add(sym.outcome_in(targets))
    assignments = dict(sym._assignments({name: current[name] for name in current}))
    for name in sym.vars:
        keep = [var == assignments[var] for var in _field_vars(sym, name)]
        if name not in free:
            opt.add(*keep)
    fields = spec.contract.field_map()
    cost = z3.IntVal(0)
    for name in free:
        same = z3.And(*[var == assignments[var] for var in _field_vars(sym, name)])
        cost = cost + z3.If(same, 0, fields[name].change_cost * 1000)
        cost = cost + _distance_terms(sym, name, fields[name], current)
    opt.minimize(cost)
    if opt.check() != z3.sat:
        return None
    return sym._extract(opt.model())


def _diff(spec: SchemeSpec, current: dict[str, Any], proposed: dict[str, Any]) -> list[dict[str, Any]]:
    changes = []
    for item in spec.contract.fields:
        old, new = current.get(item.name), proposed.get(item.name)
        if item.kind == "set":
            old, new = sorted(old or []), sorted(new or [])
        if old != new:
            changes.append({"field": item.name, "from": old, "to": new})
    return changes


def nearest_changes(
    spec: SchemeSpec,
    inputs: dict[str, Any],
    targets: list[str] | None = None,
    lock: list[str] | None = None,
    limit: int = 3,
) -> Counterfactual:
    contract = spec.contract
    current = coerce_inputs(contract, inputs)
    now = evaluate(contract, current)["outcome"]
    wanted = list(targets) if targets else list(spec.favourable)
    unknown = [t for t in wanted if t not in contract.outcomes]
    if unknown:
        raise ValueError(f"unknown target outcome {unknown}")
    if now in wanted and not targets:
        return Counterfactual(now, True)
    sym = SymbolicContract(contract)
    locked = set(lock or [])
    changeable = [f.name for f in contract.fields if f.changeable and f.name not in locked]
    result = Counterfactual(now, False)
    seen_sets: list[frozenset[str]] = []
    for size in range(1, min(MAX_FIELDS_CHANGED, len(changeable)) + 1):
        for free in combinations(changeable, size):
            if any(prior <= set(free) for prior in seen_sets):
                continue
            proposed = _solve(sym, spec, current, list(free), wanted)
            if proposed is None:
                continue
            changes = _diff(spec, current, proposed)
            used = frozenset(c["field"] for c in changes)
            if not changes or len(used) != size or used in seen_sets:
                continue
            outcome = evaluate(contract, coerce_inputs(contract, {**current, **proposed}))["outcome"]
            if outcome not in wanted:
                continue
            fields = contract.field_map()
            cost = sum(fields[c["field"]].change_cost for c in changes)
            result.alternatives.append(Alternative(changes, outcome, spec.outcome_labels.get(outcome, outcome), cost))
            seen_sets.append(used)
        if len(result.alternatives) >= limit:
            break
    result.alternatives.sort(key=lambda a: (a.cost, len(a.changes)))
    result.alternatives = result.alternatives[:limit]
    if not result.alternatives:
        blocked = _blocked_by(spec, sym, current, wanted, locked)
        result.blocked_by = blocked
    return result


def _blocked_by(spec: SchemeSpec, sym: SymbolicContract, current: dict[str, Any], wanted: list[str], locked: set[str]) -> list[str]:
    free = [f.name for f in spec.contract.fields if f.name not in locked]
    proposed = _solve(sym, spec, current, free, wanted)
    if proposed is None:
        return []
    fields = spec.contract.field_map()
    return [c["field"] for c in _diff(spec, current, proposed) if not fields[c["field"]].changeable]
