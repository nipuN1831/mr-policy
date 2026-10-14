# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""Causal graph builder for PolicySim.

Constructs a directed acyclic graph (DAG) where:
- Rule nodes represent policy rules (coloured blue in visualisation).
- Outcome nodes represent measurable business metrics (coloured green).
- Directed edges encode causal effects with direction and magnitude.

Also provides calibration from historical data to refine edge weights.
"""

from __future__ import annotations

import logging

import networkx as nx
import numpy as np

from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyRule

logger = logging.getLogger("pwt.vendor.causal.builder")

# ── Node type markers ─────────────────────────────────────────────────────────

NODE_TYPE_RULE = "rule"
NODE_TYPE_OUTCOME = "outcome"


def build_policy_graph(
    rules: list[PolicyRule],
    effects: list[PolicyEffect],
) -> nx.DiGraph:
    """Build a causal DAG from policy rules and their identified effects.

    Rule nodes are connected to outcome nodes by directed edges whose weights
    encode the direction and magnitude of the causal effect.

    Edge weight convention
    ----------------------
    - Positive weight: the cause INCREASES the effect (magnitude value).
    - Negative weight: the cause DECREASES the effect (−magnitude value).
    - Zero weight: NEUTRAL (edge is added but will have minimal impact).

    Parameters
    ----------
    rules:
        Extracted policy rules.
    effects:
        Identified causal effects between rules / outcomes.

    Returns
    -------
    nx.DiGraph
        The constructed causal DAG with node and edge attributes.
    """
    graph = nx.DiGraph()

    # Add rule nodes
    for rule in rules:
        graph.add_node(
            rule.name,
            node_type=NODE_TYPE_RULE,
            rule_id=rule.rule_id,
            condition=rule.condition,
            action=rule.action,
            confidence=rule.confidence,
        )

    # Add outcome nodes and edges
    outcome_nodes: set[str] = set()
    for effect in effects:
        # Ensure target outcome node exists
        if effect.effect not in graph:
            graph.add_node(effect.effect, node_type=NODE_TYPE_OUTCOME)
            outcome_nodes.add(effect.effect)

        # Compute signed weight
        if effect.direction == "INCREASES":
            weight = effect.magnitude
        elif effect.direction == "DECREASES":
            weight = -effect.magnitude
        else:
            weight = 0.0

        # If edge already exists (duplicate from multiple rules), average weights
        if graph.has_edge(effect.cause, effect.effect):
            existing = graph[effect.cause][effect.effect]["weight"]
            weight = (existing + weight) / 2.0
            logger.debug(
                "Averaged duplicate edge %s → %s: %.3f",
                effect.cause,
                effect.effect,
                weight,
            )

        graph.add_edge(
            effect.cause,
            effect.effect,
            weight=weight,
            direction=effect.direction,
            magnitude=effect.magnitude,
            evidence=effect.evidence,
        )

    logger.info(
        "Built causal graph: %d nodes (%d rules, %d outcomes), %d edges",
        graph.number_of_nodes(),
        len(rules),
        len(outcome_nodes),
        graph.number_of_edges(),
    )
    return graph


