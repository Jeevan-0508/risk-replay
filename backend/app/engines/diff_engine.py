"""
backend/app/engines/diff_engine.py

Deep structural diff between an original decision and a replay/counterfactual
result. Also computes sensitivity metrics. Every number here is defined by a
formula in this file -- no hidden magic scores.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import DecisionOutcome
from app.domain.models import Decision
from app.engines.replay_engine import ReplayResult


@dataclass(frozen=True)
class FieldDiff:
    field: str
    original: object
    replay: object
    changed: bool


@dataclass(frozen=True)
class DecisionDiff:
    decision_id: str
    replay_id: str
    fields: tuple[FieldDiff, ...]
    diverged: bool
    evidence_count_delta: int
    score_delta: float

    def as_table(self) -> list[dict]:
        return [
            {"field": f.field, "original": f.original, "replay": f.replay, "changed": f.changed}
            for f in self.fields
        ]


def diff_decision(decision: Decision, replay_result: ReplayResult, replay_context_evidence_count: int) -> DecisionDiff:
    fields = [
        FieldDiff("evidence_count", len(decision.context.evidence), replay_context_evidence_count,
                  len(decision.context.evidence) != replay_context_evidence_count),
        FieldDiff("risk_score", round(decision.risk_score, 4), round(replay_result.score, 4),
                   round(decision.risk_score, 4) != round(replay_result.score, 4)),
        FieldDiff("model", decision.context.model_version.model_id, "(see replay context)", False),
        FieldDiff("policy", decision.context.policy_version.policy_id, "(see replay context)", False),
        FieldDiff("decision", decision.final_outcome.value, replay_result.outcome.value,
                   decision.final_outcome != replay_result.outcome),
    ]
    diverged = decision.final_outcome != replay_result.outcome
    return DecisionDiff(
        decision_id=decision.decision_id,
        replay_id=replay_result.replay_id,
        fields=tuple(fields),
        diverged=diverged,
        evidence_count_delta=replay_context_evidence_count - len(decision.context.evidence),
        score_delta=round(replay_result.score - decision.risk_score, 4),
    )


def decision_sensitivity(original_score: float, mutated_score: float, policy_block_threshold: float) -> float:
    """How close the score sits to the decision boundary after mutation.
    0 = mutation had no effect near the boundary. 1 = mutation flipped the decision
    directly across the block threshold.
    """
    if policy_block_threshold <= 0:
        return 0.0
    delta = abs(mutated_score - original_score)
    return round(min(1.0, delta / policy_block_threshold), 4)
