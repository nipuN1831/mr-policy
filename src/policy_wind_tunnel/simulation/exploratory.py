"""Exploratory impact adapter: feeds our Contract into PolicySim's causal engine.

This is NOT a prediction. It shows how rule changes propagate through the
contract's field-reading structure, with Monte Carlo confidence intervals on
the model's own assumptions.

Weights come from measured flip-rates on our synthetic population, not from
LLM magnitude guesses.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.simulation.levers import levers
from policy_wind_tunnel.simulation.whatif import evaluate
from policy_wind_tunnel.simulation.whatif import generate_population
from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyModel, PolicyRule
from policy_wind_tunnel.third_party.policysim.simulation.engine import SimulationEngine

NOTE = "Exploratory only. Numbers are model assumptions derived from synthetic data, not predictions of real-world effect."
POPULATION_SIZE = 2000
POPULATION_SEED = 20261012


def _flip_rate(contract: Contract, rule_id: str, population: list[dict[str, Any]]) -> float:
    """Fraction of the population where this rule is the deciding rule."""
    from policy_wind_tunnel.contract.evaluator import evaluate_traced

    count = 0
    for person in population:
        try:
            _, fired = evaluate_traced(contract, person)
            if any(r == rule_id for r in fired):
                count += 1
        except Exception:
            pass
    return count / max(1, len(population))


def build_policy_model(contract: Contract) -> PolicyModel:
    """Build a PolicySim PolicyModel from our contract.

    Rules = one per contract rule.
    Effects = rule → each field it reads, weighted by measured flip rate.
    Outcome metrics = all input field names.
    Baseline stats = mean 1.0 per field (normalised; flip rates are 0-1).
    """
    population = generate_population(POPULATION_SIZE, seed=POPULATION_SEED)
    lever_report = levers(contract)
    field_names = [f.name for f in contract.fields]

    rules: list[PolicyRule] = []
    effects: list[PolicyEffect] = []

    for _, rule in contract.all_rules():
        flip = _flip_rate(contract, rule.id, population)
        lever_item = next((i for i in lever_report["levers"] if any(r["id"] == rule.id for r in i["rules"])), None)
        affected = [i["field"] for i in lever_report["levers"] if any(r["id"] == rule.id for r in i["rules"])]

        rules.append(PolicyRule(
            rule_id=rule.id,
            name=rule.id,
            condition=rule.source_quote or rule.when,
            action=rule.outcome,
            affected_outcomes=affected or field_names[:1],
            confidence=min(1.0, flip + 0.05),
        ))

        for field in affected:
            effects.append(PolicyEffect(
                cause=rule.id,
                effect=field,
                direction="INCREASES",
                magnitude=min(1.0, max(0.05, flip)),
                evidence=rule.source_quote or "",
            ))

    # deduplicate effects
    seen: set[tuple[str, str]] = set()
    unique_effects: list[PolicyEffect] = []
    for e in effects:
        if (e.cause, e.effect) not in seen:
            seen.add((e.cause, e.effect))
            unique_effects.append(e)

    nodes = [r.name for r in rules] + field_names
    edges = [{"source": e.cause, "target": e.effect, "direction": e.direction, "magnitude": e.magnitude} for e in unique_effects]
    baseline_stats = {f: {"mean": 1.0} for f in field_names}

    return PolicyModel(
        rules=rules,
        effects=unique_effects,
        outcome_metrics=field_names,
        nodes=nodes,
        edges=edges,
        source_policy=contract.name,
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        baseline_stats=baseline_stats,
    )


def run_exploratory(contract: Contract, rule_id: str, change_factor: float) -> dict[str, Any]:
    """Run a PolicySim simulation for one rule change and return a labelled result."""
    model = build_policy_model(contract)
    engine = SimulationEngine(model)
    result = engine.simulate_rule_change(
        changed_rule=rule_id,
        change_description=f"Change factor {change_factor:.2f} applied to {rule_id}",
        change_factor=change_factor,
    )
    outcomes = [
        {
            "field": o.outcome_name,
            "baseline": o.baseline_value,
            "simulated": o.simulated_value,
            "delta_pct": o.delta_pct,
            "ci_lower": o.confidence_lower,
            "ci_upper": o.confidence_upper,
            "path": o.causal_path,
        }
        for o in result.scenario_outcomes
    ]
    return {
        "changed_rule": rule_id,
        "change_factor": change_factor,
        "outcomes": outcomes,
        "overall_impact": result.overall_impact,
        "mc_runs": result.mc_runs,
        "label": "exploratory",
        "note": NOTE,
    }
