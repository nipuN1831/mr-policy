# Ported from PolicySim tests (MIT declared); build_policy_graph call signature fixed.
import networkx as nx
import pytest

from policy_wind_tunnel.third_party.policysim.causal.builder import build_policy_graph
from policy_wind_tunnel.third_party.policysim.data.schema import PolicyEffect, PolicyModel, PolicyRule


class TestBuildPolicyGraph:
    def test_returns_directed_graph(self, sample_policy_model):
        graph = build_policy_graph(sample_policy_model.rules, sample_policy_model.effects)
        assert isinstance(graph, nx.DiGraph)

    def test_nodes_include_rules_and_outcomes(self, sample_policy_model):
        graph = build_policy_graph(sample_policy_model.rules, sample_policy_model.effects)
        for rule in sample_policy_model.rules:
            assert rule.name in graph.nodes
        for metric in sample_policy_model.outcome_metrics:
            assert metric in graph.nodes

    def test_edges_reflect_effects(self, sample_policy_model):
        graph = build_policy_graph(sample_policy_model.rules, sample_policy_model.effects)
        for effect in sample_policy_model.effects:
            assert graph.has_edge(effect.cause, effect.effect), f"Expected edge {effect.cause} → {effect.effect}"

    def test_edge_has_magnitude_attribute(self, sample_policy_model):
        graph = build_policy_graph(sample_policy_model.rules, sample_policy_model.effects)
        for u, v, data in graph.edges(data=True):
            assert "magnitude" in data, f"Edge {u} → {v} missing 'magnitude'"
            assert 0.0 <= data["magnitude"] <= 1.0

    def test_graph_is_acyclic(self, sample_policy_model):
        graph = build_policy_graph(sample_policy_model.rules, sample_policy_model.effects)
        assert nx.is_directed_acyclic_graph(graph), "Policy graph contains a cycle"
