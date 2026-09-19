"""
backend/app/engines/dna_engine.py

DECISION DNA: a deterministic, human-readable summary of a decision's
forensic structure -- not an opaque embedding. Every field is either a
recorded fact (model, policy, evidence_count) or a value computed by an
existing engine (boundary_margin via boundary_engine, decision_critical
variables and governance_affected_controls via a Forensic Sweep result).

DecisionDNA never fabricates a value. If a Forensic Sweep has not been run
for this decision, decision_critical_variables and governance_affected_
controls are reported as an explicit `null` (not run), never as an empty
list pretending "nothing is critical".

integrity_status here is intentionally limited to what is genuinely checked
today: whether the decision replayed at all (see replay_engine /
replayability). It is NOT a cryptographic tamper-detection verdict -- that
is a separate, not-yet-built capability (see docs/integrity.md for the
explicit scope of what content_hash does and does not guarantee).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import ReplayabilityStatus
from app.domain.models import Decision
from app.engines import boundary_engine
from app.engines.sweep_engine import ForensicSweepResult

_INTEGRITY_BY_REPLAYABILITY = {
    ReplayabilityStatus.REPLAYABLE: "VERIFIED",
    ReplayabilityStatus.PARTIALLY_REPLAYABLE: "PARTIAL",
    ReplayabilityStatus.NON_REPLAYABLE: "UNKNOWN",
}


@dataclass(frozen=True)
class DecisionDNA:
    decision_id: str
    model: str
    policy: str
    baseline_score: float
    outcome: str
    boundary_margin: float
    zone: str
    replayability: str
    evidence_count: int
    decision_critical_variables: list[str] | None
    governance_affected_controls: list[str] | None
    integrity_status: str

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "model": self.model,
            "policy": self.policy,
            "baseline_score": self.baseline_score,
            "outcome": self.outcome,
            "boundary_margin": self.boundary_margin,
            "zone": self.zone,
            "replayability": self.replayability,
            "evidence_count": self.evidence_count,
            "decision_critical_variables": self.decision_critical_variables,
            "governance_affected_controls": self.governance_affected_controls,
            "integrity_status": self.integrity_status,
        }


def build_dna(
    decision: Decision,
    replayability_status: ReplayabilityStatus,
    sweep: ForensicSweepResult | None = None,
) -> DecisionDNA:
    """Build a DecisionDNA record.

    `sweep` is optional: if a Forensic Sweep has already been run for this
    decision (fetched from persistence, not re-run here), its results
    populate decision_critical_variables/governance_affected_controls. If
    no sweep is supplied, both fields are None -- explicitly "not computed",
    never a fabricated empty list.
    """
    policy = decision.context.policy_version
    profile = boundary_engine.analyze(decision.risk_score, policy.block_threshold, policy.review_threshold)

    critical_vars: list[str] | None = None
    affected_controls: list[str] | None = None
    if sweep is not None:
        critical_vars = [
            exp.variable for exp in sweep.experiments if exp.causal_status == "DECISION_CRITICAL"
        ]
        affected: set[str] = set()
        for exp in sweep.experiments:
            for row in exp.governance_impact:
                if row.get("changed"):
                    affected.add(row["control_id"])
        affected_controls = sorted(affected)

    return DecisionDNA(
        decision_id=decision.decision_id,
        model=policy and decision.context.model_version.model_id,
        policy=policy.policy_id,
        baseline_score=round(decision.risk_score, 4),
        outcome=decision.final_outcome.value,
        boundary_margin=profile.distance_to_block_threshold,
        zone=profile.zone,
        replayability=replayability_status.value,
        evidence_count=len(decision.context.evidence),
        decision_critical_variables=critical_vars,
        governance_affected_controls=affected_controls,
        integrity_status=_INTEGRITY_BY_REPLAYABILITY.get(replayability_status, "UNKNOWN"),
    )
