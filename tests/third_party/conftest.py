"""Fixtures for vendored PolicySim tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyModel, PolicyRule


@pytest.fixture
def sample_rules() -> list[PolicyRule]:
    return [
        PolicyRule(
            rule_id="R1",
            name="volume_discount",
            condition="when monthly order value > $500",
            action="apply 10% discount",
            affected_outcomes=["revenue", "conversion_rate", "avg_order_value"],
            confidence=0.9,
            evidence="Volume discounts apply when monthly order value exceeds $500.",
        ),
        PolicyRule(
            rule_id="R2",
            name="free_shipping",
            condition="when order total > $75",
            action="waive shipping fees",
            affected_outcomes=["conversion_rate", "avg_order_value"],
            confidence=0.85,
            evidence="Free shipping for orders above $75.",
        ),
        PolicyRule(
            rule_id="R3",
            name="surge_pricing",
            condition="when daily order volume > 150% of 30-day average",
            action="apply 5% price increase",
            affected_outcomes=["revenue", "conversion_rate"],
            confidence=0.8,
            evidence="5% surge pricing during peak demand periods.",
        ),
    ]


@pytest.fixture
def sample_effects() -> list[PolicyEffect]:
    return [
        PolicyEffect(cause="volume_discount", effect="avg_order_value", direction="INCREASES", magnitude=0.4),
        PolicyEffect(cause="volume_discount", effect="revenue", direction="DECREASES", magnitude=0.15),
        PolicyEffect(cause="free_shipping", effect="conversion_rate", direction="INCREASES", magnitude=0.5),
        PolicyEffect(cause="surge_pricing", effect="revenue", direction="INCREASES", magnitude=0.3),
        PolicyEffect(cause="surge_pricing", effect="conversion_rate", direction="DECREASES", magnitude=0.2),
        PolicyEffect(cause="avg_order_value", effect="revenue", direction="INCREASES", magnitude=0.7),
    ]


@pytest.fixture
def sample_policy_model(
    sample_rules: list[PolicyRule],
    sample_effects: list[PolicyEffect],
) -> PolicyModel:
    nodes = [r.name for r in sample_rules] + ["revenue", "conversion_rate", "avg_order_value"]
    edges = [
        {"source": e.cause, "target": e.effect, "direction": e.direction, "magnitude": e.magnitude}
        for e in sample_effects
    ]
    return PolicyModel(
        rules=sample_rules,
        effects=sample_effects,
        outcome_metrics=["revenue", "conversion_rate", "avg_order_value"],
        nodes=nodes,
        edges=edges,
        source_policy="pricing_policy.txt",
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        baseline_stats={
            "revenue": {"mean": 45000, "std": 3000, "min": 30000, "max": 60000},
            "conversion_rate": {"mean": 0.032, "std": 0.003, "min": 0.02, "max": 0.05},
            "avg_order_value": {"mean": 87.0, "std": 8.0, "min": 60.0, "max": 120.0},
        },
    )
