import json
from dataclasses import dataclass, field
from typing import Any

from policy_wind_tunnel.adversary.symbolic import SymbolicContract
from policy_wind_tunnel.contract.evaluator import ContractError, evaluate
from policy_wind_tunnel.contract.models import Contract


@dataclass(frozen=True)
class GeneratedCase:
    inputs: dict[str, Any]
    kind: str
    rule_id: str
    field: str
    note: str = ""


@dataclass
class CoverageReport:
    uncovered_rules: list[str] = field(default_factory=list)
    unreachable_rules: list[str] = field(default_factory=list)
    atom_fields_total: int = 0
    atom_fields_paired: int = 0


_CACHE: dict[str, tuple[list[GeneratedCase], CoverageReport]] = {}


class _Collector:
    def __init__(self, contract: Contract):
        self.contract = contract
        self.cases: list[GeneratedCase] = []
        self._seen: set[str] = set()

    def add(self, inputs: dict[str, Any], kind: str, rule_id: str, field_name: str, note: str = "") -> bool:
        try:
            evaluate(self.contract, inputs)
        except ContractError:
            return False
        key = json.dumps(inputs, sort_keys=True)
        if key not in self._seen:
            self._seen.add(key)
            self.cases.append(GeneratedCase(inputs, kind, rule_id, field_name, note))
        return True


def _missing_data_cases(sym: SymbolicContract, collector: _Collector) -> None:
    base = sym.base_input()
    if base is None:
        return
    for name, fv in sym.vars.items():
        if fv.spec.kind == "int" and fv.isnone is not None:
            collector.add({**base, name: None}, "missing", "", name, "value absent")
        if fv.spec.kind == "set":
            collector.add({**base, name: []}, "missing", "", name, "empty collection")


def _pair_cases(sym: SymbolicContract, rule_id: str, collector: _Collector, report: CoverageReport) -> None:
    atoms = sym.atoms_of(rule_id)
    report.atom_fields_total += sum(len(a.fields) for a in atoms)
    paired_any = False
    for atom in atoms:
        for field_name in atom.fields:
            pair = sym.solve_flip_pair(rule_id, atom, field_name)
            if pair is None:
                continue
            paired_any = True
            report.atom_fields_paired += 1
            collector.add(pair[0], "mcdc", rule_id, field_name, "boundary pair, side A")
            collector.add(pair[1], "mcdc", rule_id, field_name, "boundary pair, side B")
    if atoms and not paired_any:
        report.uncovered_rules.append(rule_id)


def generate_mcdc(contract: Contract) -> tuple[list[GeneratedCase], CoverageReport]:
    key = contract.model_dump_json()
    if key not in _CACHE:
        _CACHE[key] = _generate(contract)
    cases, report = _CACHE[key]
    return list(cases), report


def _generate(contract: Contract) -> tuple[list[GeneratedCase], CoverageReport]:
    sym = SymbolicContract(contract)
    collector = _Collector(contract)
    report = CoverageReport()
    for _, rule in contract.all_rules():
        witness = sym.solve_rule(rule.id)
        if witness is None:
            report.unreachable_rules.append(rule.id)
            continue
        collector.add(witness, "witness", rule.id, "", "satisfies the rule")
        _pair_cases(sym, rule.id, collector, report)
    _missing_data_cases(sym, collector)
    return collector.cases, report
