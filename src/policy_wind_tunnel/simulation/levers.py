from typing import Any

from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.models import Contract

NOTE = "Shows which rules read each field, directly or through derived values. It is not a causal model and predicts no real-world effect."


def _closure(contract: Contract) -> dict[str, set[str]]:
    reads: dict[str, set[str]] = {f.name: {f.name} for f in contract.fields}
    for derived in contract.derived:
        reads[derived.name] = set().union(*(reads.get(n, {n}) for n in expr.names_in(derived.expr)))
    return reads


def levers(contract: Contract) -> dict[str, Any]:
    reads = _closure(contract)
    rule_fields = [
        (rule, set().union(*(reads.get(n, {n}) for n in expr.names_in(rule.when)), set()))
        for _, rule in contract.all_rules()
    ]
    items = []
    for spec in contract.fields:
        rules = [r for r, used in rule_fields if spec.name in used]
        items.append({
            "field": spec.name,
            "description": spec.description,
            "rules": [{"id": r.id, "clause": r.clause, "outcome": r.outcome} for r in rules],
            "outcomes": sorted({r.outcome for r in rules}),
            "reasons": sorted({r.reason for r in rules if r.reason}),
        })
    items.sort(key=lambda item: (-len(item["rules"]), item["field"]))
    return {"levers": items, "note": NOTE}
