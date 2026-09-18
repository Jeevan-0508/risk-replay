"""
backend/app/engines/causal_engine.py

Turns an observed divergence (or non-divergence) into a precisely-worded
causal finding. We deliberately avoid claiming real-world causal certainty --
findings are scoped to "under the replay model", because that is exactly what
was tested. See docs/methodology.md for the reasoning.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import CausalStatus, ReplayabilityStatus
from app.engines.counterfactual_engine import CounterfactualResult


@dataclass(frozen=True)
class CausalFinding:
    decision_id: str
    mutation_summary: str
    status: CausalStatus
    explanation: str


def analyze(result: CounterfactualResult) -> CausalFinding:
    mutation_summary = "; ".join(
        f"{m.type.value} on {m.target}" for m in result.mutations
    )

    baseline_status = result.original_replay.replayability.status
    cf_status = result.counterfactual_replay.replayability.status

    if baseline_status != ReplayabilityStatus.REPLAYABLE or cf_status == ReplayabilityStatus.NON_REPLAYABLE:
        return CausalFinding(
            decision_id=result.decision_id,
            mutation_summary=mutation_summary,
            status=CausalStatus.NON_REPLAYABLE,
            explanation=(
                "This decision's context could not be fully reconstructed, so no causal "
                "claim can be made from this replay. See replayability reasons for detail."
            ),
        )

    if not result.diff.diverged:
        return CausalFinding(
            decision_id=result.decision_id,
            mutation_summary=mutation_summary,
            status=CausalStatus.DECISION_IRRELEVANT,
            explanation=(
                f"Applying [{mutation_summary}] did not change the decision outcome "
                f"under the replay model (score moved by {result.diff.score_delta})."
            ),
        )

    # Diverged: was it a clean flip (single variable) or ambiguous (multi-variable)?
    if not result.is_multi_variable:
        status = CausalStatus.DECISION_CRITICAL
        explanation = (
            f"The decision changed from {result.original_replay.outcome.value} to "
            f"{result.counterfactual_replay.outcome.value} solely because of [{mutation_summary}]. "
            f"This variable is decision-critical under the replay model."
        )
    else:
        status = CausalStatus.CONTRIBUTORY
        explanation = (
            f"The decision changed from {result.original_replay.outcome.value} to "
            f"{result.counterfactual_replay.outcome.value} after applying multiple mutations "
            f"[{mutation_summary}]. Because more than one variable changed, no single variable "
            f"can be isolated as decision-critical from this replay alone -- each would need "
            f"its own single-variable counterfactual to confirm."
        )

    return CausalFinding(
        decision_id=result.decision_id,
        mutation_summary=mutation_summary,
        status=status,
        explanation=explanation,
    )
