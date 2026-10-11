import ast
from functools import lru_cache
from typing import Any


class ExprError(Exception):
    pass


ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.USub,
    ast.BinOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.In,
    ast.NotIn,
    ast.Is,
    ast.IsNot,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.Tuple,
    ast.IfExp,
)
ALLOWED_CONSTANT_TYPES = (int, str, bool, type(None))
CONTAINER_TYPES = (tuple, frozenset, set, list)


def _check_node(node: ast.AST) -> None:
    if not isinstance(node, ALLOWED_NODES):
        raise ExprError(f"unsupported syntax: {type(node).__name__}")
    if isinstance(node, ast.Name) and node.id.startswith("_"):
        raise ExprError(f"names may not start with an underscore: {node.id}")
    if isinstance(node, ast.Constant) and not isinstance(node.value, ALLOWED_CONSTANT_TYPES):
        raise ExprError(f"unsupported constant: {node.value!r}")
    if isinstance(node, ast.Compare):
        for op, comparator in zip(node.ops, node.comparators):
            is_identity = isinstance(op, (ast.Is, ast.IsNot))
            if is_identity and not (isinstance(comparator, ast.Constant) and comparator.value is None):
                raise ExprError("'is' and 'is not' may only be used with None")


@lru_cache(maxsize=8192)
def parse(source: str) -> ast.Expression:
    try:
        tree = ast.parse(source.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError) as error:
        raise ExprError(f"cannot parse expression {source!r}: {error}") from error
    for node in ast.walk(tree):
        _check_node(node)
    return tree


def names_in(source: str) -> set[str]:
    return {node.id for node in ast.walk(parse(source)) if isinstance(node, ast.Name)}


def constants_in(source: str) -> set[int]:
    return {
        node.value
        for node in ast.walk(parse(source))
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool)
    }


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_bool(value: Any, context: str) -> bool:
    if not isinstance(value, bool):
        raise ExprError(f"{context} needs a boolean, got {value!r}")
    return value


def _require_int(value: Any, context: str) -> int:
    if not _is_int(value):
        raise ExprError(f"{context} needs an integer, got {value!r}")
    return value


def _equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is right
    if type(left) is not type(right):
        raise ExprError(f"cannot compare {left!r} with {right!r}")
    return left == right


def _compare(op: ast.cmpop, left: Any, right: Any) -> bool:
    if isinstance(op, ast.Is):
        return left is None
    if isinstance(op, ast.IsNot):
        return left is not None
    if isinstance(op, (ast.In, ast.NotIn)):
        if not isinstance(right, CONTAINER_TYPES):
            raise ExprError(f"'in' needs a collection, got {right!r}")
        return (left in right) == isinstance(op, ast.In)
    if isinstance(op, ast.Eq):
        return _equal(left, right)
    if isinstance(op, ast.NotEq):
        return not _equal(left, right)
    a = _require_int(left, "ordering comparison")
    b = _require_int(right, "ordering comparison")
    if isinstance(op, ast.Lt):
        return a < b
    if isinstance(op, ast.LtE):
        return a <= b
    if isinstance(op, ast.Gt):
        return a > b
    return a >= b


def _eval_bool_op(node: ast.BoolOp, env: dict[str, Any]) -> bool:
    is_and = isinstance(node.op, ast.And)
    for operand in node.values:
        value = _require_bool(_eval(operand, env), "boolean operator")
        if is_and and not value:
            return False
        if not is_and and value:
            return True
    return is_and


def _eval_compare(node: ast.Compare, env: dict[str, Any]) -> bool:
    left = _eval(node.left, env)
    for op, comparator in zip(node.ops, node.comparators):
        right = _eval(comparator, env)
        if not _compare(op, left, right):
            return False
        left = right
    return True


def _eval_bin_op(node: ast.BinOp, env: dict[str, Any]) -> int:
    a = _require_int(_eval(node.left, env), "arithmetic")
    b = _require_int(_eval(node.right, env), "arithmetic")
    if isinstance(node.op, ast.Add):
        return a + b
    if isinstance(node.op, ast.Sub):
        return a - b
    return a * b


def _eval(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _eval(node.body, env)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id not in env:
            raise ExprError(f"unknown name {node.id!r}")
        return env[node.id]
    if isinstance(node, ast.BoolOp):
        return _eval_bool_op(node, env)
    if isinstance(node, ast.Compare):
        return _eval_compare(node, env)
    if isinstance(node, ast.BinOp):
        return _eval_bin_op(node, env)
    if isinstance(node, ast.UnaryOp):
        operand = _eval(node.operand, env)
        if isinstance(node.op, ast.Not):
            return not _require_bool(operand, "'not'")
        return -_require_int(operand, "negation")
    if isinstance(node, ast.IfExp):
        test = _require_bool(_eval(node.test, env), "conditional")
        return _eval(node.body if test else node.orelse, env)
    if isinstance(node, ast.Tuple):
        return tuple(_eval(element, env) for element in node.elts)
    raise ExprError(f"unsupported syntax: {type(node).__name__}")


def evaluate(source: str, env: dict[str, Any]) -> Any:
    return _eval(parse(source), env)
