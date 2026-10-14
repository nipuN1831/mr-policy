# Ported from PolicySim tests (MIT declared).
import pytest

from policy_wind_tunnel.third_party.policysim.data.schema import PolicyModel, ScenarioOutcome, SimulationResult
from policy_wind_tunnel.third_party.policysim.exceptions import SimulationError
from policy_wind_tunnel.third_party.policysim.simulation.engine import SimulationEngine


class TestSimulationEngine:
    def test_returns_simulation_result(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Increase discount from 10% to 15%", change_factor=1.5)
        assert isinstance(result, SimulationResult)

    def test_result_contains_scenario_outcomes(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Test change", change_factor=1.2)
        assert len(result.scenario_outcomes) >= 1

    def test_scenario_outcome_structure(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Test change", change_factor=1.0)
        for outcome in result.scenario_outcomes:
            assert isinstance(outcome, ScenarioOutcome)
            assert outcome.confidence_lower <= outcome.simulated_value <= outcome.confidence_upper

    def test_change_factor_0_disables_rule(self, sample_policy_model):
        # change_factor=0.0 disables the rule: all outgoing edge weights become 0
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Disable rule", change_factor=0.0)
        for outcome in result.scenario_outcomes:
            assert outcome.simulated_value >= 0.0

    def test_unknown_rule_raises(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        with pytest.raises(SimulationError):
            engine.simulate_rule_change("NONEXISTENT_RULE", "...", change_factor=1.5)

    def test_result_has_recommendations(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Test", change_factor=1.3)
        assert len(result.recommendations) >= 1

    def test_mc_runs_recorded(self, sample_policy_model):
        engine = SimulationEngine(sample_policy_model)
        result = engine.simulate_rule_change("volume_discount", "Test", change_factor=1.1)
        assert result.mc_runs > 0
