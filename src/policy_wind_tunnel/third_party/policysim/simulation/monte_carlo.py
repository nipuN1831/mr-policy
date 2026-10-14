# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""Monte Carlo simulation for PolicySim.

Runs N independent simulations with Gaussian noise applied to edge weights
to estimate confidence intervals on outcome deltas.

The noise model assumes that the LLM's magnitude estimates have uncertainty
proportional to ``noise_std``.  Each run samples perturbed edge weights and
propagates the intervention effect through the graph.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np

from policy_wind_tunnel.third_party.policysim.causal.builder import NODE_TYPE_OUTCOME, build_policy_graph
from policy_wind_tunnel.third_party.policysim.data.schema import PolicyModel

logger = logging.getLogger("pwt.vendor.simulation.monte_carlo")


def monte_carlo_simulate(
    model: PolicyModel,
    changed_rule: str,
    change_factor: float,
    n_runs: int = 500,
    noise_std: float = 0.1,
) -> dict[str, tuple[float, float, float]]:
    """Run N simulations with noise on edge weights.

    For each run:
    1. Rebuild the causal graph.
    2. Apply the do-operator: multiply outgoing edges of ``changed_rule`` by
       ``change_factor`` + Gaussian noise.
    3. Propagate effects through all reachable outcome nodes.
    4. Record outcome deltas.

    The confidence interval is the 2.5th and 97.5th percentile of the delta
    distribution across all runs (95% CI).

    Parameters
    ----------
    model:
        The policy model containing rules and effects.
    changed_rule:
        Name of the rule node to intervene on.
    change_factor:
        Base multiplier for the rule's outgoing edge weights.
    n_runs:
        Number of Monte Carlo simulation runs.
    noise_std:
        Standard deviation of Gaussian noise added to edge weights per run.
        0.0 = deterministic, 0.1 = 10% relative uncertainty.

    Returns
    -------
    dict[str, tuple[float, float, float]]
        Mapping from ``outcome_name`` to ``(mean_delta, lower_ci, upper_ci)``.
        All values are absolute deltas (not percentages).
    """
    logger.info(
        "Starting Monte Carlo simulation: rule='%s', factor=%.2f, runs=%d, noise=%.2f",
        changed_rule,
        change_factor,
        n_runs,
        noise_std,
    )

    graph = build_policy_graph(model.rules, model.effects)
    outcome_metrics = model.outcome_metrics
    baseline_stats = model.baseline_stats

    # Identify outcome nodes reachable from the changed rule
    reachable_outcomes = _find_reachable_outcomes(graph, changed_rule, outcome_metrics)

    if not reachable_outcomes:
        logger.warning(
            "No outcome metrics reachable from rule '%s' — returning zero deltas",
            changed_rule,
        )
        return {m: (0.0, 0.0, 0.0) for m in outcome_metrics}

    # Collect delta samples for each outcome
    all_deltas: dict[str, list[float]] = {m: [] for m in reachable_outcomes}

    rng = np.random.default_rng(seed=42)

    for run_idx in range(n_runs):
        # Sample noisy edge weights
        noisy_graph = _apply_noisy_intervention(
            graph,
            changed_rule,
            change_factor,
            noise_std,
            rng,
        )

        # Propagate and record deltas
        run_deltas = _propagate_intervention(
            noisy_graph,
            changed_rule,
            reachable_outcomes,
            baseline_stats,
        )
        for outcome, delta in run_deltas.items():
            all_deltas[outcome].append(delta)

    # Summarise results
    results: dict[str, tuple[float, float, float]] = {}
    for outcome in outcome_metrics:
        if outcome in all_deltas and all_deltas[outcome]:
            arr = np.array(all_deltas[outcome])
            mean_delta = float(np.mean(arr))
            lower_ci = float(np.percentile(arr, 2.5))
            upper_ci = float(np.percentile(arr, 97.5))
            results[outcome] = (mean_delta, lower_ci, upper_ci)
        else:
            results[outcome] = (0.0, 0.0, 0.0)

    logger.info(
        "Monte Carlo complete: %d runs, %d outcomes with non-zero delta",
        n_runs,
        sum(1 for _, (m, lo, hi) in results.items() if abs(m) > 1e-9),
    )
    return results


# ── Internal helpers ──────────────────────────────────────────────────────────


def _find_reachable_outcomes(
    graph: nx.DiGraph,
    source: str,
    outcome_metrics: list[str],
) -> list[str]:
    """Return outcome metrics reachable from ``source`` via directed edges."""
    if source not in graph:
        return []
    reachable = nx.descendants(graph, source)
    return [m for m in outcome_metrics if m in reachable]


def _apply_noisy_intervention(
    graph: nx.DiGraph,
    changed_rule: str,
    change_factor: float,
    noise_std: float,
    rng: np.random.Generator,
) -> nx.DiGraph:
    """Return a copy of the graph with the do-operator applied with noise.

    All outgoing edges from ``changed_rule`` have their weight multiplied by
    ``change_factor`` plus independent Gaussian noise.
    """
    g = graph.copy()
    for _, target in list(g.out_edges(changed_rule)):
        original_weight = g[changed_rule][target]["weight"]
        noise = rng.normal(0.0, noise_std) if noise_std > 0.0 else 0.0
        noisy_factor = change_factor + noise
        # Clamp factor so direction is preserved (weight sign unchanged)
        noisy_factor = max(0.0, noisy_factor) if original_weight >= 0 else noisy_factor
        g[changed_rule][target]["weight"] = original_weight * noisy_factor
    return g


def _propagate_intervention(
    graph: nx.DiGraph,
    source: str,
    reachable_outcomes: list[str],
    baseline_stats: dict[str, dict[str, float]],
) -> dict[str, float]:
    """Propagate the intervention effect and compute absolute deltas.

    Uses a linear additive model: for each path from ``source`` to an outcome,
    the effect is the product of edge weights along the path, applied to the
    outcome's baseline mean value.

    Multiple paths are summed (total causal effect = sum of path effects).
    """
    deltas: dict[str, float] = {}

    for outcome in reachable_outcomes:
        if outcome not in graph:
            continue

        baseline_mean = baseline_stats.get(outcome, {}).get("mean", 1.0)

        # Find all simple paths and accumulate effects
        total_effect = 0.0
        try:
            paths = list(nx.all_simple_paths(graph, source=source, target=outcome, cutoff=6))
        except nx.NetworkXError:
            paths = []

        for path in paths:
            path_weight = 1.0
            for i in range(len(path) - 1):
                edge_weight = graph[path[i]][path[i + 1]].get("weight", 0.0)
                path_weight *= edge_weight
            total_effect += path_weight

        # Delta = baseline × total_effect (linear causal model)
        deltas[outcome] = baseline_mean * total_effect

    return deltas
