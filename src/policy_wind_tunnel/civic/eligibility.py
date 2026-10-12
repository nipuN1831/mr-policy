from dataclasses import dataclass, field
from typing import Any

from policy_wind_tunnel.contract.evaluator import evaluate_traced
from policy_wind_tunnel.contract.models import Contract

DISCLAIMER = (
    "Indicative result only. This is not legal advice and not an official decision; the issuing office decides. "
    "Check the cited source and its date before acting. Nothing you enter is stored."
)


class SchemeError(Exception):
    pass


class UnknownScheme(SchemeError):
    pass


class NotCheckable(SchemeError):
    pass


@dataclass
class SchemeSpec:
    id: str
    country: str
    name: str
    contract: Contract
    policy_text: str
    favourable: list[str]
    outcome_labels: dict[str, str]
    source: dict[str, Any]
    reason_labels: dict[str, str] = field(default_factory=dict)


def _registry() -> dict[str, SchemeSpec]:
    from policy_wind_tunnel.civic import scheme_defs

    return scheme_defs.specs()


def _pack_schemes() -> list[tuple[str, Any]]:
    from policy_wind_tunnel.civic.packs import available_countries, load_pack

    return [(c["code"], s) for c in available_countries() for s in load_pack(c["code"]).schemes]


def list_schemes() -> list[dict[str, Any]]:
    registry = _registry()
    listing = [
        {"id": s.id, "country": s.country, "name": s.name, "self_check": True} for s in registry.values()
    ]
    listing += [
        {"id": s.id, "country": code, "name": s.name, "self_check": False}
        for code, s in _pack_schemes()
        if s.id not in registry
    ]
    return listing


def get_scheme(scheme_id: str) -> SchemeSpec:
    registry = _registry()
    if scheme_id in registry:
        return registry[scheme_id]
    if any(s.id == scheme_id for _, s in _pack_schemes()):
        raise NotCheckable(
            "This scheme cannot be checked here: eligibility is decided by a caseworker or a government database, "
            "and no numeric rule could be verified from an official page."
        )
    raise UnknownScheme(f"unknown scheme {scheme_id!r}")


def check(scheme_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    spec = get_scheme(scheme_id)
    result, fired = evaluate_traced(spec.contract, inputs)
    rules = {rule.id: rule for _, rule in spec.contract.all_rules()}
    clauses = [
        {
            "rule_id": rule_id,
            "clause": rules[rule_id].clause,
            "quote": rules[rule_id].source_quote,
            "reason": rules[rule_id].reason,
        }
        for rule_id in fired
    ]
    return {
        "scheme": spec.id,
        "name": spec.name,
        "outcome": result["outcome"],
        "outcome_label": spec.outcome_labels.get(result["outcome"], result["outcome"]),
        "favourable": result["outcome"] in spec.favourable,
        "reasons": result["reasons"],
        "reason_labels": [spec.reason_labels.get(r, r) for r in result["reasons"]],
        "clauses": clauses,
        "source": spec.source,
        "disclaimer": DISCLAIMER,
    }


def form_spec(scheme_id: str) -> dict[str, Any]:
    spec = get_scheme(scheme_id)
    fields = []
    for item in spec.contract.fields:
        entry: dict[str, Any] = {
            "name": item.name,
            "label": item.description or item.name,
            "kind": item.kind,
            "nullable": item.nullable,
            "min": item.min,
            "max": item.max,
            "changeable": item.changeable,
            "typical": item.typical,
        }
        if item.kind in ("enum", "set"):
            entry["options"] = [{"value": v, "label": item.labels.get(v, v)} for v in item.values]
        fields.append(entry)
    return {
        "id": spec.id,
        "name": spec.name,
        "country": spec.country,
        "fields": fields,
        "policy_text": spec.policy_text,
        "source": spec.source,
        "assumptions": [
            {"id": a.id, "clause": a.clause, "question": a.question, "resolution": a.resolution}
            for a in spec.contract.ambiguities
        ],
        "outcomes": [
            {"outcome": o, "label": spec.outcome_labels.get(o, o), "favourable": o in spec.favourable}
            for o in spec.contract.outcomes
        ],
    }
