import random

from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.baseline import BASELINE_CASES
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.samples import random_inputs
from policy_wind_tunnel.contract.evaluator import evaluate
from policy_wind_tunnel.contract.gold import LENDING_CONTRACT


def test_gold_contract_agrees_with_reference_engine_on_random_inputs():
    reference = wrap_engine(decide)
    rng = random.Random(20261011)
    for _ in range(30000):
        inputs = random_inputs(rng)
        assert evaluate(LENDING_CONTRACT, inputs) == reference(inputs), inputs


def test_gold_contract_agrees_with_reference_engine_on_the_baseline_cases():
    reference = wrap_engine(decide)
    for inputs, expected in BASELINE_CASES:
        assert evaluate(LENDING_CONTRACT, inputs) == reference(inputs) == expected
