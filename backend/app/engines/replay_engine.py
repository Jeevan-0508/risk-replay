"""
backend/app/engines/replay_engine.py

Deterministic replay. A replay NEVER reaches into current production state --
it only ever operates on the DecisionContext object it is given (the original,
or a mutated copy of it). This module also owns the replayability assessment:
if a context is missing something required to replay, we say so explicitly
rather than silently substituting current state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums import DecisionOutcome, NonReplayableReason, ReplayabilityStatus
from app.domain.models import Decision, DecisionContext
from app.engines.decision_engine import ScoringBreakdown, decide


@dataclass(frozen=True)
class ReplayabilityAssessment:
    status: ReplayabilityStatus
    reasons: tuple[NonReplayableReason, ...] = ()
    details: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayResult:
    replay_id: str
    decision_id: str
    context_hash: str
    outcome: DecisionOutcome
    score: float
    breakdown: ScoringBreakdown
    replayability: ReplayabilityAssessment
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def matches_original(self) -> bool | None:
        return None  # comparison is the comparator's job, not the replay's


def assess_replayability(context: DecisionContext) -> ReplayabilityAssessment:
    reasons: list[NonReplayableReason] = []
    details: list[str] = []

    if context.input_snapshot is None or not context.input_snapshot.content_hash:
        reasons.append(NonReplayableReason.MISSING_INPUT)
        details.append("Input snapshot has no content hash recorded.")

    if context.model_version is None or not context.model_version.model_id:
        reasons.append(NonReplayableReason.MISSING_MODEL_VERSION)
        details.append("No model version bound to this context.")

    if context.policy_version is None or not context.policy_version.policy_id:
        reasons.append(NonReplayableReason.MISSING_POLICY_VERSION)
        details.append("No policy version bound to this context.")

    for ev in context.evidence:
        if not ev.content_hash:
            reasons.append(NonReplayableReason.PROVENANCE_GAP)
            details.append(f"Evidence {ev.evidence_id} has no content hash.")

    non_deterministic_tools = [t for t in context.tool_invocations if not t.deterministic]
    if non_deterministic_tools:
        reasons.append(NonReplayableReason.NON_DETERMINISTIC_TOOL)
        details.append(
            "Non-deterministic tool output(s): "
            + ", ".join(t.tool_id for t in non_deterministic_tools)
        )

    if not reasons:
        return ReplayabilityAssessment(status=ReplayabilityStatus.REPLAYABLE)

    # Missing model/policy/input make full replay impossible; other issues are partial.
    blocking = {
        NonReplayableReason.MISSING_INPUT,
        NonReplayableReason.MISSING_MODEL_VERSION,
        NonReplayableReason.MISSING_POLICY_VERSION,
    }
    if blocking.intersection(reasons):
        status = ReplayabilityStatus.NON_REPLAYABLE
    else:
        status = ReplayabilityStatus.PARTIALLY_REPLAYABLE

    return ReplayabilityAssessment(status=status, reasons=tuple(reasons), details=tuple(details))


def replay(decision: Decision, context: DecisionContext | None = None, replay_id: str = "") -> ReplayResult:
    """Replay a decision. If `context` is provided, replay against THAT context
    (used by the counterfactual engine after a mutation). Otherwise replay
    against the decision's own recorded context (sanity / determinism check).
    """
    ctx = context if context is not None else decision.context
    assessment = assess_replayability(ctx)

    if assessment.status == ReplayabilityStatus.NON_REPLAYABLE:
        # We still compute what we can for transparency, but flag it clearly.
        outcome, score, breakdown = decide(ctx)
    else:
        outcome, score, breakdown = decide(ctx)

    return ReplayResult(
        replay_id=replay_id or f"REPLAY-{decision.decision_id}-{ctx.context_hash()[:8]}",
        decision_id=decision.decision_id,
        context_hash=ctx.context_hash(),
        outcome=outcome,
        score=score,
        breakdown=breakdown,
        replayability=assessment,
    )
