from datetime import datetime, timezone

import pytest

from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyModel, PolicyRule


@pytest.fixture
def sample_rules():
    return [
        PolicyRule(rule_id="R1", name="volume_discount", condition="when monthly order value > $500", action="apply 10% discount", affected_outcomes=["revenue", "conversion_rate", "avg_order_value"], confidence=0.9),
        PolicyRule(rule_id="R2", name="free_shipping", condition="when order total > $75", action="waive shipping fees", affected_outcomes=["conversion_rate", "avg_order_value"], confidence=0.85),
        PolicyRule(rule_id="R3", name="surge_pricing", condition="when daily volume high", action="apply 5% price increase", affected_outcomes=["revenue", "conversion_rate"], confidence=0.8),
    ]


@pytest.fixture
def sample_effects():
    return [
        PolicyEffect(cause="volume_discount", effect="avg_order_value", direction="INCREASES", magnitude=0.4),
        PolicyEffect(cause="volume_discount", effect="revenue", direction="DECREASES", magnitude=0.15),
        PolicyEffect(cause="free_shipping", effect="conversion_rate", direction="INCREASES", magnitude=0.5),
        PolicyEffect(cause="surge_pricing", effect="revenue", direction="INCREASES", magnitude=0.3),
        PolicyEffect(cause="surge_pricing", effect="conversion_rate", direction="DECREASES", magnitude=0.2),
        PolicyEffect(cause="avg_order_value", effect="revenue", direction="INCREASES", magnitude=0.7),
    ]


@pytest.fixture
def sample_policy_model(sample_rules, sample_effects):
    metrics = ["revenue", "conversion_rate", "avg_order_value"]
    return PolicyModel(
        rules=sample_rules,
        effects=sample_effects,
        outcome_metrics=metrics,
        nodes=[r.name for r in sample_rules] + metrics,
        edges=[{"source": e.cause, "target": e.effect, "direction": e.direction, "magnitude": e.magnitude} for e in sample_effects],
        source_policy="pricing_policy.txt",
        created_at=datetime.now(tz=timezone.utc).isoformat(),
        baseline_stats={
            "revenue": {"mean": 45000.0},
            "conversion_rate": {"mean": 0.032},
            "avg_order_value": {"mean": 87.0},
        },
    )
