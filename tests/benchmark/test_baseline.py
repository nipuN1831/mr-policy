from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.baseline import BASELINE_CASES
from policy_wind_tunnel.benchmark.engine import decide


def test_baseline_has_a_realistic_size():
    assert 12 <= len(BASELINE_CASES) <= 20


def test_baseline_passes_on_reference_engine():
    run = wrap_engine(decide)
    for inputs, expected in BASELINE_CASES:
        assert run(inputs) == expected, inputs
