import pytest

from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.expr import ExprError


def ev(source, **env):
    return expr.evaluate(source, env)


def test_arithmetic_and_comparison():
    assert ev("(a + b) * 100 > 45 * c", a=10, b=5, c=30) is True
    assert ev("(a + b) * 100 > 45 * c", a=10, b=5, c=40) is False


def test_boundaries_are_exact_integers():
    assert ev("income >= 25000", income=25000) is True
    assert ev("income >= 25000", income=24999) is False


def test_boolean_operators_short_circuit_around_none():
    assert ev("score is None or score > 3", score=None) is True
    assert ev("score is not None and score > 3", score=None) is False


def test_ordering_against_none_is_an_error_not_false():
    with pytest.raises(ExprError):
        ev("score > 3", score=None)


def test_ternary_and_not():
    assert ev("680 if ok and not bad else 700", ok=True, bad=False) == 680
    assert ev("680 if ok and not bad else 700", ok=True, bad=True) == 700


def test_membership_in_sets_and_tuples():
    assert ev('"id_proof" in docs', docs=frozenset({"id_proof"})) is True
    assert ev('"id_proof" not in docs', docs=frozenset()) is True
    assert ev('kind in ("a", "b")', kind="b") is True


def test_chained_comparison():
    assert ev("21 <= age <= 65", age=65) is True
    assert ev("21 <= age <= 65", age=66) is False


def test_non_bool_operand_in_boolean_context_is_rejected():
    with pytest.raises(ExprError):
        ev("a and b", a=1, b=True)


def test_bool_is_not_an_integer_for_arithmetic():
    with pytest.raises(ExprError):
        ev("a + 1", a=True)


def test_unknown_name_is_an_error():
    with pytest.raises(ExprError):
        ev("missing > 1")


@pytest.mark.parametrize(
    "source",
    [
        "__import__('os')",
        "a.b",
        "f(1)",
        "lambda: 1",
        "a[0]",
        "a / 2",
        "a ** 2",
        "a // 2",
        "1.5 < a",
        "[x for x in a]",
        "a if b",
        "_hidden > 1",
        "(a := 1)",
        "a;b",
        "",
    ],
)
def test_unsafe_or_unsupported_syntax_is_rejected_at_parse_time(source):
    with pytest.raises(ExprError):
        expr.parse(source)


def test_names_in_returns_every_referenced_name():
    assert expr.names_in('(a + b) * 100 > 45 * c and "x" in d') == {"a", "b", "c", "d"}


def test_constants_in_returns_integer_constants():
    assert expr.constants_in("a >= 21 and a <= 65 or b * 100 > 45 * c") == {21, 65, 100, 45}
