# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""Causal graph validator for PolicySim.

Validates the structural integrity of the causal DAG:
- No directed cycles (must be a true DAG).
- All edge endpoints connect to known nodes.
- Warns if isolated nodes exist (no edges).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import networkx as nx

logger = logging.getLogger("pwt.vendor.causal.validator")


@dataclass
class ValidationReport:
    """Result of validating a causal graph.

    Attributes
    ----------
    is_valid:
        ``True`` if the graph passed all hard checks.
    node_count:
        Total number of nodes in the graph.
    edge_count:
        Total number of directed edges in the graph.
    errors:
        Fatal validation errors (graph will not be usable).
    warnings:
        Non-fatal issues (graph is usable but may produce unexpected results).
    """

    is_valid: bool
    node_count: int
    edge_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_policy_graph(graph: nx.DiGraph) -> ValidationReport:
    """Validate the structural integrity of a policy causal graph.

    Checks
    ------
    1. (Hard) No directed cycles — the graph must be a DAG.
    2. (Hard) All edge endpoints must be nodes in the graph.
    3. (Soft) Isolated nodes (no edges) produce a warning.
    4. (Soft) Edges with zero weight produce a warning.

    Parameters
    ----------
    graph:
        The causal DAG to validate.

    Returns
    -------
    ValidationReport
        Validation results with errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # ── Hard check 1: cycle detection ─────────────────────────────────────
    if not nx.is_directed_acyclic_graph(graph):
        cycles = list(nx.simple_cycles(graph))
        cycle_strs = [" → ".join(c + [c[0]]) for c in cycles[:3]]
        errors.append(
            f"Causal graph contains {len(cycles)} directed cycle(s). "
            f"DAG structure is violated. Cycles detected: {cycle_strs}"
        )
        logger.error("Cycle detected in causal graph: %s", cycle_strs)
    else:
        logger.debug("Cycle check passed: graph is a DAG")

    # ── Hard check 2: edge endpoints exist as nodes ────────────────────────
    all_nodes = set(graph.nodes())
    for u, v in graph.edges():
        if u not in all_nodes:
            errors.append(f"Edge source '{u}' is not a registered node.")
        if v not in all_nodes:
            errors.append(f"Edge target '{v}' is not a registered node.")

    # ── Soft check 3: isolated nodes ──────────────────────────────────────
    isolated = [n for n in graph.nodes() if graph.degree(n) == 0]
    if isolated:
        warnings.append(
            f"Isolated node(s) with no edges (will not participate in simulation): "
            f"{isolated}"
        )
        logger.warning("Isolated nodes found: %s", isolated)

    # ── Soft check 4: zero-weight edges ───────────────────────────────────
    zero_weight = [
        (u, v)
        for u, v, d in graph.edges(data=True)
        if abs(d.get("weight", 1.0)) < 1e-9
    ]
    if zero_weight:
        warnings.append(
            f"Edge(s) with near-zero weight (negligible causal effect): "
            f"{[(u, v) for u, v in zero_weight[:5]]}"
        )

    is_valid = len(errors) == 0
    report = ValidationReport(
        is_valid=is_valid,
        node_count=graph.number_of_nodes(),
        edge_count=graph.number_of_edges(),
        errors=errors,
        warnings=warnings,
    )

    if is_valid:
        logger.info(
            "Graph validation passed: %d nodes, %d edges, %d warning(s)",
            report.node_count,
            report.edge_count,
            len(warnings),
        )
    else:
        logger.error(
            "Graph validation FAILED: %d error(s), %d warning(s)",
            len(errors),
            len(warnings),
        )

    return report
