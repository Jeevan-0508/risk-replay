"""
backend/app/engines/risk_engine.py

Deterministic risk metrics. Every metric has a documented formula.
No metric here is randomly generated or LLM-derived.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import RiskLevel
from app.domain.models import Decision
from app.engines.counterfactual_engine import CounterfactualResult


@dataclass(frozen=True)
class RiskAssessment:
    decision_id: str
    decision_risk: float          # = risk_score itself, already 0..1
    evidence_completeness: float  # fraction of evidence items with a content hash
    provenance_completeness: float  # fraction of (evidence + input) with a content hash
    control_coverage: float       # fraction of required controls that were evaluated
    policy_violation_count: int
    replay_divergence: float | None       # None if no counterfactual has been run yet
    decision_sensitivity: float | None
    risk_level: RiskLevel
    formulas: dict


def _risk_level(score: float) -> RiskLevel:
    if score >= 0.85:
        return RiskLevel.CRITICAL
    if score >= 0.6:
        return RiskLevel.HIGH
    if score >= 0.3:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def assess_risk(decision: Decision, counterfactual: CounterfactualResult | None = None) -> RiskAssessment:
    ctx = decision.context
    evidence = ctx.evidence

    evidence_completeness = (
        sum(1 for e in evidence if e.content_hash) / len(evidence) if evidence else 0.0
    )
    provenance_items = list(evidence) + [ctx.input_snapshot]
    provenance_completeness = (
        sum(1 for x in provenance_items if x.content_hash) / len(provenance_items)
        if provenance_items else 0.0
    )

    required = set(ctx.policy_version.required_controls)
    evaluated = {c.control_id for c in decision.controls}
    control_coverage = (
        len(required & evaluated) / len(required) if required else 1.0
    )

    policy_violation_count = sum(1 for c in decision.controls if c.status == "FAILED")

    replay_divergence = None
    decision_sensitivity = None
    if counterfactual is not None:
        replay_divergence = 1.0 if counterfactual.diff.diverged else 0.0
        threshold = ctx.policy_version.block_threshold
        decision_sensitivity = (
            round(min(1.0, abs(counterfactual.diff.score_delta) / threshold), 4)
            if threshold > 0 else 0.0
        )

    return RiskAssessment(
        decision_id=decision.decision_id,
        decision_risk=round(decision.risk_score, 4),
        evidence_completeness=round(evidence_completeness, 4),
        provenance_completeness=round(provenance_completeness, 4),
        control_coverage=round(control_coverage, 4),
        policy_violation_count=policy_violation_count,
        replay_divergence=replay_divergence,
        decision_sensitivity=decision_sensitivity,
        risk_level=_risk_level(decision.risk_score),
        formulas={
            "decision_risk": "risk_score computed by decision_engine.decide() at decision time",
            "evidence_completeness": "count(evidence with content_hash) / count(evidence)",
            "provenance_completeness": "count(provenance items with content_hash) / count(all provenance items)",
            "control_coverage": "count(required_controls evaluated) / count(required_controls)",
            "policy_violation_count": "count(controls where status == FAILED)",
            "replay_divergence": "1.0 if counterfactual outcome != original outcome else 0.0",
            "decision_sensitivity": "min(1, abs(score_delta) / policy.block_threshold)",
        },
    )


def blast_radius(decisions: list[Decision], changed_replays: list[CounterfactualResult]) -> dict:
    """Aggregate impact of a hypothetical model/policy change across many decisions."""
    total = len(decisions)
    changed = [r for r in changed_replays if r.diff.diverged]
    to_review = [r for r in changed if r.counterfactual_replay.outcome.value == "REVIEW"]
    high_risk = [r for r in changed if abs(r.diff.score_delta) >= 0.2]
    return {
        "affected_decisions": total,
        "decision_changes": len(changed),
        "human_review_changes": len(to_review),
        "high_risk_changes": len(high_risk),
        "no_change": total - len(changed),
    }
