# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""Simulation engine for PolicySim.

Implements the do-operator: modifies edge weights for the changed rule,
propagates effects through the causal graph, and computes outcome deltas.

The propagation model is a linear additive model:
    outcome_delta = sum over all paths(rule → outcome) of:
        product of edge weights along path × change_factor × baseline_value

Monte Carlo confidence intervals are computed by adding Gaussian noise to
edge weights across N simulation runs.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import numpy as np

from policy_wind_tunnel.third_party.policysim.causal.builder import NODE_TYPE_OUTCOME, build_policy_graph
from policy_wind_tunnel.third_party.policysim.causal.validator import validate_policy_graph
from policy_wind_tunnel.third_party.policysim.data.schema import PolicyModel, ScenarioOutcome, SimulationResult
from policy_wind_tunnel.third_party.policysim.exceptions import InsufficientDataError, SimulationError
from policy_wind_tunnel.third_party.policysim.simulation.monte_carlo import monte_carlo_simulate

logger = logging.getLogger("pwt.vendor.simulation")


class SimulationEngine:
    """Simulates the effect of changing a policy rule on outcome metrics.

    Parameters
    ----------
    model:
        The ``PolicyModel`` to simulate against.
    """

    def __init__(self, model: PolicyModel) -> None:
        self._model = model
        self._graph = self._rebuild_graph()

    # ── Public API ────────────────────────────────────────────────────────

    def simulate_rule_change(
        self,
        changed_rule: str,
        change_description: str,
        change_factor: float = 1.0,
    ) -> SimulationResult:
        """Simulate the effect of changing a rule.

        Applies the do-operator by multiplying all outgoing edge weights of
        ``changed_rule`` by ``change_factor``, then propagates the change
        through the causal graph to compute deltas on all reachable outcome
        metrics.

        Monte Carlo simulation is used to derive confidence intervals.

        Parameters
        ----------
        changed_rule:
            The ``name`` of the rule node to intervene on.
        change_description:
            Human-readable description of the change (stored in result).
        change_factor:
            Multiplier applied to the rule's effect magnitudes.
            1.0 = no change, 2.0 = double the effect, 0.0 = disable the rule.

        Returns
        -------
        SimulationResult
            Full simulation result with per-outcome deltas and CIs.

        Raises
        ------
        SimulationError
            If the rule does not exist in the model or has no causal effects.
        """
        if changed_rule not in self._graph:
            available = [
                n for n, d in self._graph.nodes(data=True)
                if d.get("node_type") == "rule" or n == changed_rule
            ]
            raise SimulationError(
                f"Rule '{changed_rule}' not found in the causal graph. "
                f"Available rule nodes: {available}"
            )

        successors = list(self._graph.successors(changed_rule))
        if not successors:
            raise SimulationError(
                f"Rule '{changed_rule}' has no outgoing causal edges. "
                f"Cannot simulate its effects."
            )

        logger.info(
            "Simulating rule change: rule='%s', factor=%.2f, description='%s'",
            changed_rule,
            change_factor,
            change_description,
        )

        # Run Monte Carlo simulation for confidence intervals
        mc_results = monte_carlo_simulate(
            model=self._model,
            changed_rule=changed_rule,
            change_factor=change_factor,
            n_runs=self._model_mc_runs,
            noise_std=0.1,
        )

        # Build ScenarioOutcome for each affected metric
        scenario_outcomes: list[ScenarioOutcome] = []
        baseline_stats = self._model.baseline_stats

        for outcome_name in self._model.outcome_metrics:
            if outcome_name not in mc_results:
                continue

            mean_delta, lower_ci, upper_ci = mc_results[outcome_name]

            baseline = baseline_stats.get(outcome_name, {}).get("mean", 0.0)
            simulated = baseline + mean_delta
            delta_pct = (mean_delta / baseline * 100.0) if abs(baseline) > 1e-9 else 0.0

            # Find causal path
            try:
                path = nx.shortest_path(self._graph, source=changed_rule, target=outcome_name)
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                path = [changed_rule, outcome_name]

            scenario_outcomes.append(
                ScenarioOutcome(
                    outcome_name=outcome_name,
                    baseline_value=round(baseline, 4),
                    simulated_value=round(simulated, 4),
                    delta=round(mean_delta, 4),
                    delta_pct=round(delta_pct, 2),
                    causal_path=path,
                    confidence_lower=round(baseline + lower_ci, 4),
                    confidence_upper=round(baseline + upper_ci, 4),
                )
            )

        if not scenario_outcomes:
            raise SimulationError(
                f"Rule '{changed_rule}' affects no outcome metrics in this model. "
                f"Check that the rule has outgoing edges to outcome nodes."
            )

        # Generate human-readable summary and recommendations
        overall_impact = self._generate_impact_summary(scenario_outcomes, changed_rule, change_factor)
        recommendations = self._generate_recommendations(scenario_outcomes, change_factor)

        return SimulationResult(
            changed_rule=changed_rule,
            change_description=change_description,
            scenario_outcomes=scenario_outcomes,
            overall_impact=overall_impact,
            recommendations=recommendations,
            mc_runs=self._model_mc_runs,
            confidence_level=0.95,
        )

    # ── Internals ─────────────────────────────────────────────────────────

    def _rebuild_graph(self) -> nx.DiGraph:
        """Reconstruct the NetworkX graph from the serialised PolicyModel."""
        from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyRule

        rules = self._model.rules
        effects = self._model.effects
        graph = build_policy_graph(rules, effects)

        validation = validate_policy_graph(graph)
        if not validation.is_valid:
            raise SimulationError(
                f"Causal graph is invalid: {validation.errors}"
            )
        return graph

    @property
    def _model_mc_runs(self) -> int:
        """Return the number of MC runs from the model or default."""
        return getattr(self._model, "mc_runs", 500) or 500

    @staticmethod
    def _generate_impact_summary(
        outcomes: list[ScenarioOutcome],
        rule: str,
        factor: float,
    ) -> str:
        """Generate a concise human-readable impact summary."""
        if factor == 0.0:
            action = "disabling"
        elif factor > 1.0:
            action = f"strengthening (×{factor:.1f})"
        elif factor < 1.0:
            action = f"weakening (×{factor:.1f})"
        else:
            action = "applying (×1.0)"

        positive = [o for o in outcomes if o.delta > 0]
        negative = [o for o in outcomes if o.delta < 0]
        neutral = [o for o in outcomes if abs(o.delta) < 1e-9]

        lines = [f"Simulated impact of {action} rule '{rule}':"]
        if positive:
            lines.append(
                f"  Projected INCREASE in: "
                + ", ".join(f"{o.outcome_name} (+{o.delta_pct:.1f}%)" for o in positive)
            )
        if negative:
            lines.append(
                f"  Projected DECREASE in: "
                + ", ".join(f"{o.outcome_name} ({o.delta_pct:.1f}%)" for o in negative)
            )
        if neutral:
            lines.append(
                f"  No significant change in: {', '.join(o.outcome_name for o in neutral)}"
            )
        return "\n".join(lines)

    @staticmethod
    def _generate_recommendations(
        outcomes: list[ScenarioOutcome],
        change_factor: float,
    ) -> list[str]:
        """Generate simple data-driven recommendations."""
        recommendations: list[str] = []

        revenue_outcomes = [o for o in outcomes if "revenue" in o.outcome_name]
        churn_outcomes = [o for o in outcomes if "churn" in o.outcome_name]
        cost_outcomes = [o for o in outcomes if "cost" in o.outcome_name]

        for o in revenue_outcomes:
            if o.delta_pct < -5.0:
                recommendations.append(
                    f"Revenue is projected to drop by {abs(o.delta_pct):.1f}%. "
                    f"Consider a smaller change factor or offset with another rule."
                )
            elif o.delta_pct > 5.0:
                recommendations.append(
                    f"Revenue is projected to increase by {o.delta_pct:.1f}%. "
                    f"This appears to be a favourable change."
                )

        for o in churn_outcomes:
            if o.delta_pct > 2.0:
                recommendations.append(
                    f"Churn rate may increase by {o.delta_pct:.1f}%. "
                    f"Monitor customer satisfaction closely after rollout."
                )
            elif o.delta_pct < -2.0:
                recommendations.append(
                    f"Churn rate is projected to decrease by {abs(o.delta_pct):.1f}%. "
                    f"This suggests improved customer retention."
                )

        for o in cost_outcomes:
            if o.delta_pct > 10.0:
                recommendations.append(
                    f"Discount/operational cost may increase by {o.delta_pct:.1f}%. "
                    f"Review budget impact before implementing."
                )

        if not recommendations:
            recommendations.append(
                "Simulated impacts appear modest. Validate with a pilot programme "
                "before full rollout."
            )

        return recommendations
