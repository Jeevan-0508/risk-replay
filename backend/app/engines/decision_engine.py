"""
backend/app/engines/decision_engine.py

The deterministic rule engine that turns a DecisionContext into a decision.
This is intentionally NOT an LLM and NOT a black-box ML model: it is a
transparent, inspectable scoring function so that every score in this system
can be explained by a formula, per the project's non-negotiable design rule.

score = base_rate + sum(evidence.value * evidence.weight for evidence in context)
        clamped to [0, 1]

decision:
    score >= policy.block_threshold  -> BLOCK
    score >= policy.review_threshold -> REVIEW
    else                             -> ALLOW
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import DecisionOutcome
from app.domain.models import DecisionContext


@dataclass(frozen=True)
class ScoringBreakdown:
    base_rate: float
    contributions: dict  # evidence_id -> contribution value
    raw_score: float
    clamped_score: float


def score_context(context: DecisionContext) -> ScoringBreakdown:
    weights = context.model_version.weights
    contributions: dict[str, float] = {}
    total = context.model_version.base_rate
    for ev in context.evidence:
        w = weights.get(ev.kind, ev.weight)
        contribution = ev.value * w
        contributions[ev.evidence_id] = contribution
        total += contribution
    clamped = max(0.0, min(1.0, total))
    return ScoringBreakdown(
        base_rate=context.model_version.base_rate,
        contributions=contributions,
        raw_score=total,
        clamped_score=clamped,
    )


def decide(context: DecisionContext) -> tuple[DecisionOutcome, float, ScoringBreakdown]:
    breakdown = score_context(context)
    score = breakdown.clamped_score
    policy = context.policy_version
    if score >= policy.block_threshold:
        outcome = DecisionOutcome.BLOCK
    elif score >= policy.review_threshold:
        outcome = DecisionOutcome.REVIEW
    else:
        outcome = DecisionOutcome.ALLOW
    return outcome, score, breakdown
