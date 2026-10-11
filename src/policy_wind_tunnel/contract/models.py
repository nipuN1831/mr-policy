import keyword
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from policy_wind_tunnel.contract import expr
from policy_wind_tunnel.contract.expr import ExprError


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FieldSpec(Strict):
    name: str
    kind: Literal["int", "str", "bool", "enum", "set"]
    nullable: bool = False
    min: int | None = None
    max: int | None = None
    values: list[str] = Field(default_factory=list)
    typical: Any = None
    description: str = ""

    @model_validator(mode="after")
    def check(self) -> "FieldSpec":
        if not self.name.isidentifier() or keyword.iskeyword(self.name) or self.name.startswith("_"):
            raise ValueError(f"invalid field name {self.name!r}")
        if self.kind in ("enum", "set") and not self.values:
            raise ValueError(f"field {self.name} of kind {self.kind} needs values")
        return self


class Derived(Strict):
    name: str
    expr: str
    clause: str
    source_quote: str = ""


class Rule(Strict):
    id: str
    clause: str
    source_quote: str = ""
    when: str
    outcome: str
    reason: str | None = None


class Stage(Strict):
    name: str
    mode: Literal["first_match", "collect"]
    rules: list[Rule] = Field(min_length=1)


class Ambiguity(Strict):
    id: str
    clause: str
    question: str
    resolution: str
    status: Literal["proposed", "approved", "rejected"] = "proposed"


class Contract(Strict):
    name: str
    description: str = ""
    outcomes: list[str] = Field(min_length=1)
    fields: list[FieldSpec] = Field(min_length=1)
    derived: list[Derived] = Field(default_factory=list)
    stages: list[Stage] = Field(min_length=1)
    ambiguities: list[Ambiguity] = Field(default_factory=list)

    @model_validator(mode="after")
    def check(self) -> "Contract":
        known = self._check_names()
        self._check_derived(known)
        self._check_rules(known)
        return self

    def _check_names(self) -> set[str]:
        names = [f.name for f in self.fields]
        if len(set(names)) != len(names):
            raise ValueError("duplicate field names")
        return set(names)

    def _check_derived(self, known: set[str]) -> None:
        for derived in self.derived:
            if derived.name in known:
                raise ValueError(f"derived name {derived.name!r} collides with an earlier name")
            self._check_expression(derived.expr, known, f"derived {derived.name}")
            known.add(derived.name)

    def _check_rules(self, known: set[str]) -> None:
        seen_ids: set[str] = set()
        for stage in self.stages:
            for rule in stage.rules:
                if rule.id in seen_ids:
                    raise ValueError(f"duplicate rule id {rule.id!r}")
                seen_ids.add(rule.id)
                if rule.outcome not in self.outcomes:
                    raise ValueError(f"rule {rule.id} uses undeclared outcome {rule.outcome!r}")
                self._check_expression(rule.when, known, f"rule {rule.id}")

    @staticmethod
    def _check_expression(source: str, known: set[str], owner: str) -> None:
        try:
            used = expr.names_in(source)
        except ExprError as error:
            raise ValueError(f"{owner}: {error}") from error
        unknown = used - known
        if unknown:
            raise ValueError(f"{owner} uses unknown names {sorted(unknown)}")

    def field_map(self) -> dict[str, FieldSpec]:
        return {f.name: f for f in self.fields}

    def all_rules(self) -> list[tuple[Stage, Rule]]:
        return [(stage, rule) for stage in self.stages for rule in stage.rules]
