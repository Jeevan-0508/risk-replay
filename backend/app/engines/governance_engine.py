"""
backend/app/engines/governance_engine.py

Deterministic governance / control checks. Every control evaluation is a pure
function of the DecisionContext -- never an LLM judgment call.

Supported control rules (ControlDefinition.rule):
  - "human_review_above_review_threshold": requires a HumanOverride to be present
     if the score crossed the policy's review_threshold.
  - "required_evidence_present": requires every evidence "kind" named in the
     control description's payload to be present.
  - "approved_model_version": model_id must be in an allowed set (passed in).
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import GovernanceStatus
from app.domain.models import ControlEvaluation, Decision


@dataclass(frozen=True)
class GovernanceFinding:
    control_id: str
    control_name: str
    status: GovernanceStatus
    reason: str
    evidence: tuple[str, ...]


def evaluate_controls(decision: Decision, approved_model_ids: set[str] | None = None) -> list[GovernanceFinding]:
    findings: list[GovernanceFinding] = []
    ctx = decision.context

    for control in ctx.control_definitions:
        if control.rule == "human_review_above_review_threshold":
            crossed = decision.risk_score >= ctx.policy_version.review_threshold
            has_override = decision.human_override is not None
            if crossed and not has_override:
                findings.append(GovernanceFinding(
                    control_id=control.control_id,
                    control_name=control.name,
                    status=GovernanceStatus.FAILED,
                    reason=(
                        f"Decision {decision.decision_id} crossed the configured review "
                        f"threshold ({ctx.policy_version.review_threshold}) but no human "
                        f"override/review was recorded."
                    ),
                    evidence=(decision.decision_id, ctx.policy_version.policy_id, control.control_id),
                ))
            else:
                findings.append(GovernanceFinding(
                    control_id=control.control_id, control_name=control.name,
                    status=GovernanceStatus.SATISFIED,
                    reason="Review threshold not crossed, or human override present.",
                    evidence=(decision.decision_id,),
                ))

        elif control.rule == "approved_model_version":
            allowed = approved_model_ids or set()
            ok = ctx.model_version.model_id in allowed if allowed else True
            findings.append(GovernanceFinding(
                control_id=control.control_id, control_name=control.name,
                status=GovernanceStatus.SATISFIED if ok else GovernanceStatus.FAILED,
                reason=(
                    "Model version is on the approved list."
                    if ok else f"Model version {ctx.model_version.model_id} is not on the approved list."
                ),
                evidence=(ctx.model_version.model_id,),
            ))

        elif control.rule == "required_evidence_present":
            present_kinds = {e.kind for e in ctx.evidence}
            required_kinds = set(control.description.split(",")) if control.description else set()
            missing = required_kinds - present_kinds
            findings.append(GovernanceFinding(
                control_id=control.control_id, control_name=control.name,
                status=GovernanceStatus.SATISFIED if not missing else GovernanceStatus.FAILED,
                reason="All required evidence kinds present." if not missing
                       else f"Missing required evidence kinds: {sorted(missing)}",
                evidence=tuple(sorted(present_kinds)),
            ))
        else:
            findings.append(GovernanceFinding(
                control_id=control.control_id, control_name=control.name,
                status=GovernanceStatus.NOT_APPLICABLE,
                reason=f"Unknown control rule '{control.rule}'; not evaluated.",
                evidence=(),
            ))

    return findings


def to_control_evaluations(findings: list[GovernanceFinding]) -> tuple[ControlEvaluation, ...]:
    return tuple(
        ControlEvaluation(control_id=f.control_id, status=f.status.value, reason=f.reason)
        for f in findings
    )
