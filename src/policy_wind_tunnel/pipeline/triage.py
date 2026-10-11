from dataclasses import dataclass, field

from policy_wind_tunnel.contract.models import Contract
from policy_wind_tunnel.pipeline.runner import Finding

SEVERITY_BY_ACTUAL = {"REJECT": "high", "APPROVE": "high", "INCOMPLETE": "medium", "REFER": "medium"}


@dataclass
class Cluster:
    key: str
    clause: str
    verdict: str
    severity: str
    findings: list[Finding]
    representative: Finding
    summary: str
    ambiguity_id: str = ""


@dataclass
class TriageReport:
    clusters: list[Cluster] = field(default_factory=list)

    @property
    def defect_count(self) -> int:
        return sum(1 for c in self.clusters if c.verdict == "defect")

    @property
    def clarification_count(self) -> int:
        return sum(1 for c in self.clusters if c.verdict == "needs_clarification")


def _cluster_key(finding: Finding) -> str:
    actual = finding.actual.get("outcome", finding.kind)
    return f"{finding.kind}|{finding.rule_id}|{finding.expected['outcome']}->{actual}"


def _distance(finding: Finding) -> tuple[int, int]:
    outcome_matches = finding.expected["outcome"] == finding.actual.get("outcome")
    return int(outcome_matches), sum(len(str(v)) for v in finding.inputs.values())


def _severity(findings: list[Finding]) -> str:
    sample = findings[0]
    if sample.kind in ("crash", "timeout"):
        return "high"
    if sample.expected["outcome"] == sample.actual.get("outcome"):
        return "low"
    return SEVERITY_BY_ACTUAL.get(sample.actual.get("outcome", ""), "medium")


def _ambiguity_for(contract: Contract, clause: str) -> str:
    for item in contract.ambiguities:
        if item.clause == clause and item.status != "approved":
            return item.id
    return ""


def _summary(finding: Finding, count: int) -> str:
    if finding.kind in ("crash", "timeout"):
        return f"Implementation {finding.kind} on {count} input(s) for clause {finding.clause}"
    expected = finding.expected["outcome"]
    actual = finding.actual.get("outcome", "?")
    suffix = "s" if count != 1 else ""
    return f"Clause {finding.clause}: expected {expected} but implementation returned {actual} on {count} input{suffix}"


def triage(contract: Contract, findings: list[Finding]) -> TriageReport:
    groups: dict[str, list[Finding]] = {}
    for finding in findings:
        groups.setdefault(_cluster_key(finding), []).append(finding)
    clusters = []
    for key, members in groups.items():
        representative = min(members, key=_distance)
        ambiguity = _ambiguity_for(contract, representative.clause)
        clusters.append(
            Cluster(
                key=key,
                clause=representative.clause,
                verdict="needs_clarification" if ambiguity else "defect",
                severity=_severity(members),
                findings=members,
                representative=representative,
                summary=_summary(representative, len(members)),
                ambiguity_id=ambiguity,
            )
        )
    clusters.sort(key=lambda c: ({"high": 0, "medium": 1, "low": 2}[c.severity], c.clause, c.key))
    return TriageReport(clusters)
