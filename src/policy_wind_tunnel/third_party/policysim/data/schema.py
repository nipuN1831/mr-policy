# Vendored from https://github.com/opencausality/PolicySim @ 3d3d3d4 (MIT declared in pyproject.toml; no LICENSE file present). See third_party/policysim/NOTICE.md.
"""Pydantic data models for PolicySim.

These models define the core data structures used throughout the application:
- PolicyRule: a single rule extracted from a policy document
- PolicyEffect: a causal effect between a rule and an outcome metric
- ScenarioOutcome: the simulated outcome of a single metric after a rule change
- SimulationResult: the full result of simulating a policy rule change
- PolicyModel: the complete causal model derived from policy + data
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    """A single actionable rule extracted from a policy document.

    Attributes
    ----------
    rule_id:
        Short identifier, e.g. ``"R1"``.
    name:
        Human-readable rule name, e.g. ``"volume_discount"``.
    condition:
        Trigger condition in natural language, e.g. ``"when monthly order value > $500"``.
    action:
        What the rule does when triggered, e.g. ``"apply 10% discount"``.
    affected_outcomes:
        List of business metric names this rule is expected to influence.
    confidence:
        Extraction confidence (0.0–1.0).  Rules below the configured threshold
        are excluded from the causal graph.
    evidence:
        Exact text passage from the policy document that this rule was extracted from.
    """

    rule_id: str
    name: str
    condition: str
    action: str
    affected_outcomes: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: str = ""


class PolicyEffect(BaseModel):
    """A causal relationship between a rule (or outcome) and an outcome metric.

    Attributes
    ----------
    cause:
        The rule name or upstream outcome metric that drives the effect.
    effect:
        The downstream outcome metric that is affected.
    direction:
        Whether the cause increases, decreases, or is neutral on the effect.
    magnitude:
        Estimated normalised effect size (0.0 = no effect, 1.0 = full effect).
    evidence:
        Textual evidence or reasoning supporting this causal link.
    """

    cause: str
    effect: str
    direction: Literal["INCREASES", "DECREASES", "NEUTRAL"]
    magnitude: float = Field(ge=0.0, le=1.0)
    evidence: str = ""


class ScenarioOutcome(BaseModel):
    """The simulated outcome for a single metric after a rule change.

    Attributes
    ----------
    outcome_name:
        The name of the outcome metric (e.g. ``"revenue"``).
    baseline_value:
        Historical mean value of this metric before the simulated change.
    simulated_value:
        Projected value after the rule change.
    delta:
        Absolute difference: ``simulated_value - baseline_value``.
    delta_pct:
        Percentage change relative to baseline.
    causal_path:
        Ordered list of nodes from changed rule to this outcome in the graph.
    confidence_lower:
        Lower bound of the 95% confidence interval for ``simulated_value``.
    confidence_upper:
        Upper bound of the 95% confidence interval for ``simulated_value``.
    """

    outcome_name: str
    baseline_value: float
    simulated_value: float
    delta: float
    delta_pct: float
    causal_path: list[str]
    confidence_lower: float
    confidence_upper: float


class SimulationResult(BaseModel):
    """Full result of simulating a policy rule change.

    Attributes
    ----------
    changed_rule:
        The name of the rule that was changed.
    change_description:
        Natural-language description of what was changed.
    scenario_outcomes:
        Per-metric simulation results.
    overall_impact:
        Human-readable summary of the overall simulated impact.
    recommendations:
        Suggested actions based on the simulation.
    mc_runs:
        Number of Monte Carlo runs used to compute confidence intervals.
    confidence_level:
        Statistical confidence level for the intervals (default 0.95).
    """

    changed_rule: str
    change_description: str
    scenario_outcomes: list[ScenarioOutcome]
    overall_impact: str
    recommendations: list[str]
    mc_runs: int
    confidence_level: float = 0.95


class PolicyModel(BaseModel):
    """Full causal model extracted from policy documents and outcome data.

    This is the serialisable artefact produced by ``policysim build`` and
    consumed by ``policysim simulate``.

    Attributes
    ----------
    rules:
        All extracted policy rules.
    effects:
        All identified causal effects between rules and metrics.
    outcome_metrics:
        Names of the outcome metrics in the historical data.
    nodes:
        All node names in the causal DAG (rules + outcome metrics).
    edges:
        Serialised edge list: each entry is a dict with keys
        ``source``, ``target``, ``direction``, ``magnitude``.
    source_policy:
        Path or title of the original policy document.
    created_at:
        ISO-8601 timestamp of when this model was built.
    baseline_stats:
        Descriptive statistics for each outcome metric (mean, std, etc.).
    """

    rules: list[PolicyRule]
    effects: list[PolicyEffect]
    outcome_metrics: list[str]
    nodes: list[str]
    edges: list[dict]
    source_policy: str
    created_at: str
    baseline_stats: dict[str, dict[str, float]] = Field(default_factory=dict)
