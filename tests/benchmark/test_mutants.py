import random

from policy_wind_tunnel.benchmark.adapter import wrap_engine
from policy_wind_tunnel.benchmark.baseline import BASELINE_CASES
from policy_wind_tunnel.benchmark.engine import decide
from policy_wind_tunnel.benchmark.mutants import MUTANTS, build_mutant
from policy_wind_tunnel.benchmark.samples import random_inputs


def test_catalogue_has_ten_unique_mutants_with_clause_references():
    ids = [m.id for m in MUTANTS]
    assert len(ids) == 10
    assert len(set(ids)) == 10
    assert all(m.clause.startswith("L") for m in MUTANTS)
    assert all(m.description for m in MUTANTS)


def test_every_mutant_differs_from_the_reference_on_some_input():
    reference = wrap_engine(decide)
    rng = random.Random(1234)
    samples = [random_inputs(rng) for _ in range(30000)]
    for mutant in MUTANTS:
        run = wrap_engine(build_mutant(mutant.id))
        assert any(run(s) != reference(s) for s in samples), mutant.id


def test_baseline_misses_a_meaningful_share_of_mutants():
    reference_cases = BASELINE_CASES
    survivors = []
    for mutant in MUTANTS:
        run = wrap_engine(build_mutant(mutant.id))
        if all(run(inputs) == expected for inputs, expected in reference_cases):
            survivors.append(mutant.id)
    assert 4 <= len(survivors) <= 8, survivors


def test_mutants_do_not_affect_the_reference_engine():
    before = wrap_engine(decide)(BASELINE_CASES[0][0])
    build_mutant(MUTANTS[0].id)
    assert wrap_engine(decide)(BASELINE_CASES[0][0]) == before
