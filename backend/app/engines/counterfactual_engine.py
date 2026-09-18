"""
backend/app/engines/counterfactual_engine.py

Runs "what if" replays: apply mutation(s) to a decision's frozen context,
replay against the mutated context, and produce a structured comparison.
Never touches the original Decision object.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.models import Decision
from app.engines.diff_engine import DecisionDiff, diff_decision
from app.engines.mutation_engine import Mutation, apply_mutations
from app.engines.replay_engine import ReplayResult, replay


@dataclass(frozen=True)
class CounterfactualResult:
    counterfactual_id: str
    decision_id: str
    mutations: tuple[Mutation, ...]
    original_replay: ReplayResult
    counterfactual_replay: ReplayResult
    diff: DecisionDiff
    is_multi_variable: bool
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def run_counterfactual(decision: Decision, mutations: list[Mutation], counterfactual_id: str = "") -> CounterfactualResult:
    if not mutations:
        raise ValueError("At least one mutation is required to run a counterfactual.")

    original_replay = replay(decision, context=decision.context,
                             replay_id=f"BASELINE-{decision.decision_id}")

    mutated_context = apply_mutations(decision.context, mutations)
    counterfactual_replay = replay(decision, context=mutated_context,
                                    replay_id=f"CF-{decision.decision_id}-{len(mutations)}")

    diff = diff_decision(decision, counterfactual_replay, len(mutated_context.evidence))

    return CounterfactualResult(
        counterfactual_id=counterfactual_id or f"COUNTERFACTUAL-{decision.decision_id}-{mutations[0].mutation_id}",
        decision_id=decision.decision_id,
        mutations=tuple(mutations),
        original_replay=original_replay,
        counterfactual_replay=counterfactual_replay,
        diff=diff,
        is_multi_variable=len(mutations) > 1,
    )
