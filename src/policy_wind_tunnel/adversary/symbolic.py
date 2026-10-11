import ast
from dataclasses import dataclass, field
from typing import Any

import z3

from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.models import Contract, FieldSpec

DISTANCE_WEIGHT = 20
EQUALITY_WEIGHT = 5
SAME_FIELD_WEIGHT = 3
ISOLATION_WEIGHT = 10
ORDERING_KINDS = (z3.Z3_OP_LE, z3.Z3_OP_GE, z3.Z3_OP_LT, z3.Z3_OP_GT)


class Unsupported(Exception):
    pass


@dataclass(frozen=True)
class _NoneValue:
    pass


@dataclass(frozen=True)
class _StrValue:
    value: str


@dataclass
class FieldVars:
    spec: FieldSpec
    val: Any = None
    isnone: Any = None
    flag: Any = None
    members: dict[str, Any] = field(default_factory=dict)

    def all_vars(self) -> list[Any]:
        found = [self.val, self.isnone, self.flag, *self.members.values()]
        return [v for v in found if v is not None]


@dataclass(frozen=True)
class _IntField:
    fv: FieldVars


@dataclass(frozen=True)
class _EnumField:
    fv: FieldVars


@dataclass(frozen=True)
class _SetField:
    fv: FieldVars


@dataclass(frozen=True)
class Atom:
    term: Any
    fields: tuple[str, ...]
    lhs: Any = None
    rhs: Any = None


_NONE = _NoneValue()


def _make_vars(spec: FieldSpec) -> FieldVars:
    name = spec.name
    if spec.kind == "int":
        return FieldVars(spec, val=z3.Int(name), isnone=z3.Bool(f"{name}__none") if spec.nullable else None)
    if spec.kind == "enum":
        return FieldVars(spec, val=z3.Int(name))
    if spec.kind == "bool" and not spec.nullable:
        return FieldVars(spec, flag=z3.Bool(name))
    if spec.kind == "set":
        return FieldVars(spec, members={v: z3.Bool(f"{name}__has__{v}") for v in spec.values})
    raise Unsupported(f"field {name} of kind {spec.kind} (nullable={spec.nullable}) is not supported symbolically")


def _domain(fv: FieldVars) -> list[Any]:
    spec = fv.spec
    if spec.kind == "enum":
        return [fv.val >= 0, fv.val < len(spec.values)]
    if spec.kind != "int":
        return []
    bounds = []
    if spec.min is not None:
        bounds.append(fv.val >= spec.min)
    if spec.max is not None:
        bounds.append(fv.val <= spec.max)
    if fv.isnone is None:
        return bounds
    within = z3.And(*bounds) if bounds else z3.BoolVal(True)
    return [z3.Or(fv.isnone, within), z3.Implies(fv.isnone, fv.val == 0)]


def _anchor_terms(fv: FieldVars) -> list[Any]:
    spec, typical = fv.spec, fv.spec.typical
    if typical is None:
        return []
    if spec.kind == "int":
        return [z3.And(z3.Not(fv.isnone), fv.val == typical)] if fv.isnone is not None else [fv.val == typical]
    if spec.kind == "enum":
        return [fv.val == spec.values.index(typical)]
    if spec.kind == "bool":
        return [fv.flag == bool(typical)]
    return [fv.members[v] == (v in typical) for v in spec.values]


class SymbolicContract:
    def __init__(self, contract: Contract):
        self.contract = contract
        self.vars = {spec.name: _make_vars(spec) for spec in contract.fields}
        self.domain = [d for fv in self.vars.values() for d in _domain(fv)]
        self._var_field = {v.decl().name(): name for name, fv in self.vars.items() for v in fv.all_vars()}
        self._when: dict[str, Any] = {}
        self._stage_of: dict[str, int] = {}
        self._fire: dict[str, Any] = {}
        self._stage_any: list[Any] = []
        self._build()

    def _initial_env(self) -> dict[str, Any]:
        env: dict[str, Any] = {}
        for name, fv in self.vars.items():
            kind = fv.spec.kind
            env[name] = {"int": _IntField, "enum": _EnumField, "set": _SetField}.get(kind, lambda f: f.flag)(fv)
        return env

    def _build(self) -> None:
        env = self._initial_env()
        for derived in self.contract.derived:
            env[derived.name] = self._translate(expr.parse(derived.expr), env)
        reach = z3.BoolVal(True)
        for stage_index, stage in enumerate(self.contract.stages):
            whens = []
            for rule in stage.rules:
                when = self._as_bool(self._translate(expr.parse(rule.when), env))
                prior = [z3.Not(p) for p in whens] if stage.mode == "first_match" else []
                self._when[rule.id] = when
                self._stage_of[rule.id] = stage_index
                self._fire[rule.id] = z3.And(reach, when, *prior)
                whens.append(when)
            any_fire = z3.Or(*whens)
            self._stage_any.append(any_fire)
            reach = z3.And(reach, z3.Not(any_fire))

    def _as_bool(self, value: Any) -> Any:
        if isinstance(value, z3.BoolRef):
            return value
        raise Unsupported(f"expected a boolean term, got {value!r}")

    def _as_int(self, value: Any) -> Any:
        if isinstance(value, _IntField):
            return value.fv.val
        if isinstance(value, _EnumField):
            raise Unsupported("enum values cannot be used in arithmetic")
        if isinstance(value, z3.ArithRef):
            return value
        raise Unsupported(f"expected an integer term, got {value!r}")

    def _translate(self, node: ast.AST, env: dict[str, Any]) -> Any:
        if isinstance(node, ast.Expression):
            return self._translate(node.body, env)
        if isinstance(node, ast.Constant):
            return self._constant(node.value)
        if isinstance(node, ast.Name):
            return env[node.id]
        if isinstance(node, ast.BoolOp):
            terms = [self._as_bool(self._translate(v, env)) for v in node.values]
            return z3.And(*terms) if isinstance(node.op, ast.And) else z3.Or(*terms)
        if isinstance(node, ast.UnaryOp):
            operand = self._translate(node.operand, env)
            return z3.Not(self._as_bool(operand)) if isinstance(node.op, ast.Not) else -self._as_int(operand)
        if isinstance(node, ast.BinOp):
            return self._binary(node, env)
        if isinstance(node, ast.IfExp):
            test = self._as_bool(self._translate(node.test, env))
            return z3.If(test, self._translate(node.body, env), self._translate(node.orelse, env))
        if isinstance(node, ast.Tuple):
            return tuple(self._translate(e, env) for e in node.elts)
        if isinstance(node, ast.Compare):
            return self._compare_chain(node, env)
        raise Unsupported(f"unsupported syntax {type(node).__name__}")

    @staticmethod
    def _constant(value: Any) -> Any:
        if value is None:
            return _NONE
        if isinstance(value, bool):
            return z3.BoolVal(value)
        if isinstance(value, int):
            return z3.IntVal(value)
        return _StrValue(value)

    def _binary(self, node: ast.BinOp, env: dict[str, Any]) -> Any:
        a = self._as_int(self._translate(node.left, env))
        b = self._as_int(self._translate(node.right, env))
        if isinstance(node.op, ast.Add):
            return a + b
        if isinstance(node.op, ast.Sub):
            return a - b
        return a * b

    def _compare_chain(self, node: ast.Compare, env: dict[str, Any]) -> Any:
        left = self._translate(node.left, env)
        parts = []
        for op, comparator in zip(node.ops, node.comparators):
            right = self._translate(comparator, env)
            parts.append(self._compare(op, left, right))
            left = right
        return parts[0] if len(parts) == 1 else z3.And(*parts)

    def _compare(self, op: ast.cmpop, left: Any, right: Any) -> Any:
        if isinstance(op, ast.Is):
            return self._is_none(left)
        if isinstance(op, ast.IsNot):
            return z3.Not(self._is_none(left))
        if isinstance(op, ast.In):
            return self._contains(left, right)
        if isinstance(op, ast.NotIn):
            return z3.Not(self._contains(left, right))
        if isinstance(op, ast.Eq):
            return self._equals(left, right)
        if isinstance(op, ast.NotEq):
            return z3.Not(self._equals(left, right))
        return self._ordering(type(op), self._as_int(left), self._as_int(right))

    def _ordering(self, op: type, a: Any, b: Any) -> Any:
        if z3.is_app_of(a, z3.Z3_OP_ITE):
            return z3.If(a.arg(0), self._ordering(op, a.arg(1), b), self._ordering(op, a.arg(2), b))
        if z3.is_app_of(b, z3.Z3_OP_ITE):
            return z3.If(b.arg(0), self._ordering(op, a, b.arg(1)), self._ordering(op, a, b.arg(2)))
        return {ast.Lt: lambda: a < b, ast.LtE: lambda: a <= b, ast.Gt: lambda: a > b, ast.GtE: lambda: a >= b}[op]()

    @staticmethod
    def _is_none(value: Any) -> Any:
        if isinstance(value, _NoneValue):
            return z3.BoolVal(True)
        if isinstance(value, _IntField) and value.fv.isnone is not None:
            return value.fv.isnone
        return z3.BoolVal(False)

    def _equals(self, left: Any, right: Any) -> Any:
        if isinstance(left, _NoneValue) or isinstance(right, _NoneValue):
            return self._is_none(right if isinstance(left, _NoneValue) else left)
        if isinstance(left, _EnumField) and isinstance(right, _StrValue):
            return self._enum_is(left, right.value)
        if isinstance(right, _EnumField) and isinstance(left, _StrValue):
            return self._enum_is(right, left.value)
        if isinstance(left, z3.BoolRef) and isinstance(right, z3.BoolRef):
            return left == right
        return self._as_int(left) == self._as_int(right)

    @staticmethod
    def _enum_is(enum: _EnumField, value: str) -> Any:
        values = enum.fv.spec.values
        return enum.fv.val == values.index(value) if value in values else z3.BoolVal(False)

    def _contains(self, left: Any, right: Any) -> Any:
        if isinstance(right, _SetField):
            if not isinstance(left, _StrValue):
                raise Unsupported("set membership needs a string literal on the left")
            return right.fv.members.get(left.value, z3.BoolVal(False))
        if isinstance(right, tuple):
            return z3.Or(*[self._equals(left, element) for element in right]) if right else z3.BoolVal(False)
        raise Unsupported("'in' needs a set field or a tuple")

    def rule_ids(self) -> list[str]:
        return list(self._fire)

    def atoms_of(self, rule_id: str) -> list[Atom]:
        seen: set[int] = set()
        found: list[Atom] = []

        def walk(term: Any) -> None:
            if term.get_id() in seen:
                return
            seen.add(term.get_id())
            if self._is_atom(term):
                found.append(self._make_atom(term))
                return
            for child in term.children():
                walk(child)

        walk(self._when[rule_id])
        return found

    @staticmethod
    def _is_atom(term: Any) -> bool:
        if not z3.is_bool(term):
            return False
        if z3.is_const(term):
            return term.decl().kind() == z3.Z3_OP_UNINTERPRETED
        if z3.is_app(term) and term.decl().kind() in ORDERING_KINDS:
            return True
        return z3.is_eq(term) and z3.is_arith(term.arg(0))

    def _make_atom(self, term: Any) -> Atom:
        names: list[str] = []

        def collect(t: Any) -> None:
            if z3.is_const(t) and t.decl().kind() == z3.Z3_OP_UNINTERPRETED:
                owner = self._var_field.get(t.decl().name())
                if owner and owner not in names:
                    names.append(owner)
                return
            for child in t.children():
                collect(child)

        collect(term)
        is_ordering = z3.is_app(term) and term.decl().kind() in ORDERING_KINDS
        lhs, rhs = (term.arg(0), term.arg(1)) if is_ordering else (None, None)
        return Atom(term, tuple(names), lhs, rhs)

    def _anchors(self, skip: str | None = None) -> list[Any]:
        return [t for name, fv in self.vars.items() if name != skip for t in _anchor_terms(fv)]

    def _extract(self, model: Any, rename: dict[Any, Any] | None = None) -> dict[str, Any]:
        def value_of(var: Any) -> Any:
            return model.eval((rename or {}).get(var, var), model_completion=True)

        inputs: dict[str, Any] = {}
        for name, fv in self.vars.items():
            spec = fv.spec
            if spec.kind == "int":
                is_none = fv.isnone is not None and z3.is_true(value_of(fv.isnone))
                inputs[name] = None if is_none else value_of(fv.val).as_long()
            elif spec.kind == "enum":
                inputs[name] = spec.values[value_of(fv.val).as_long()]
            elif spec.kind == "bool":
                inputs[name] = z3.is_true(value_of(fv.flag))
            else:
                inputs[name] = [v for v in spec.values if z3.is_true(value_of(fv.members[v]))]
        return inputs

    def _assignments(self, inputs: dict[str, Any]) -> list[tuple[Any, Any]]:
        pairs: list[tuple[Any, Any]] = []
        for name, fv in self.vars.items():
            spec, value = fv.spec, inputs.get(name)
            if spec.kind == "int":
                pairs.append((fv.val, z3.IntVal(0 if value is None else value)))
                if fv.isnone is not None:
                    pairs.append((fv.isnone, z3.BoolVal(value is None)))
            elif spec.kind == "enum":
                pairs.append((fv.val, z3.IntVal(spec.values.index(value))))
            elif spec.kind == "bool":
                pairs.append((fv.flag, z3.BoolVal(bool(value))))
            else:
                pairs.extend((fv.members[v], z3.BoolVal(v in (value or ()))) for v in spec.values)
        return pairs

    def fired_rules(self, inputs: dict[str, Any]) -> set[str]:
        pairs = self._assignments(inputs)
        return {rid for rid, term in self._fire.items() if z3.is_true(z3.simplify(z3.substitute(term, *pairs)))}

    def _solve(self, constraints: list[Any], anchored: bool = True) -> dict[str, Any] | None:
        opt = z3.Optimize()
        opt.add(self.domain)
        opt.add(constraints)
        if anchored:
            for term in self._anchors():
                opt.add_soft(term)
        return self._extract(opt.model()) if opt.check() == z3.sat else None

    def can_fire(self, rule_id: str) -> bool:
        return self._solve([self._fire[rule_id]], anchored=False) is not None

    def solve_rule(self, rule_id: str) -> dict[str, Any] | None:
        return self._solve([self._fire[rule_id]])

    def base_input(self) -> dict[str, Any] | None:
        return self._solve([])

    def find_uncovered_input(self) -> dict[str, Any] | None:
        return self._solve([z3.Not(z3.Or(*self._stage_any))], anchored=False)

    def _second_copy(self) -> dict[Any, Any]:
        return {v: z3.Const(f"{v.decl().name()}__b", v.sort()) for fv in self.vars.values() for v in fv.all_vars()}

    def solve_flip_pair(self, rule_id: str, atom: Atom, field_name: str) -> tuple[dict, dict] | None:
        copy = self._second_copy()
        swap = list(copy.items())

        def second(term: Any) -> Any:
            return z3.substitute(term, *swap)

        fire = self._fire[rule_id]
        opt = z3.Optimize()
        opt.add(self.domain)
        opt.add([second(d) for d in self.domain])
        for name, fv in self.vars.items():
            if name != field_name:
                opt.add([v == copy[v] for v in fv.all_vars()])
        opt.add(z3.Xor(fire, second(fire)))
        opt.add(atom.term)
        opt.add(z3.Not(second(atom.term)))
        for term in self._anchors(skip=field_name):
            opt.add_soft(term)
        for other_id, when in self._when.items():
            if other_id != rule_id and self._stage_of[other_id] <= self._stage_of[rule_id]:
                opt.add_soft(z3.Not(when), weight=ISOLATION_WEIGHT)
                opt.add_soft(z3.Not(second(when)), weight=ISOLATION_WEIGHT)
        self._add_pair_preferences(opt, atom, self.vars[field_name], copy, second)
        if opt.check() != z3.sat:
            return None
        model = opt.model()
        return self._extract(model), self._extract(model, copy)

    @staticmethod
    def _add_pair_preferences(opt: Any, atom: Atom, fv: FieldVars, copy: dict, second: Any) -> None:
        if atom.lhs is not None:
            at_boundary = atom.lhs == atom.rhs
            opt.add_soft(z3.Or(at_boundary, second(at_boundary)), weight=EQUALITY_WEIGHT)
        if fv.spec.kind == "int":
            opt.add_soft(z3.Or(copy[fv.val] == fv.val + 1, copy[fv.val] == fv.val - 1), weight=DISTANCE_WEIGHT)
        atom_vars = {t.decl().name() for t in _consts(atom.term)}
        for var in fv.all_vars():
            if var.decl().name() not in atom_vars and fv.spec.kind != "int":
                opt.add_soft(var == copy[var], weight=SAME_FIELD_WEIGHT)


def _consts(term: Any) -> list[Any]:
    if z3.is_const(term) and term.decl().kind() == z3.Z3_OP_UNINTERPRETED:
        return [term]
    return [c for child in term.children() for c in _consts(child)]
