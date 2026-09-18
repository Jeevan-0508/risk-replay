"""
backend/app/engines/sweep_engine.py

FORENSIC SWEEP: automatic, deterministic, single-variable counterfactual
testing across every variable in a decision's context that can be safely and
meaningfully removed/disabled without inventing a hypothetical new value.

Non-negotiable design rules (see docs/forensic-sweep.md for the full writeup):
  - Pure, deterministic. Same decision -> same mutation set, same order,
    every time. No randomness, no LLM, no network call.
  - Every experiment starts from the SAME frozen baseline (decision.context).
    Mutation A never leaks into mutation B -- each experiment calls
    counterfactual_engine.run_counterfactual() with exactly one mutation
    applied to a fresh copy of the original context.
  - This module does not duplicate scoring, diffing, causal wording, or
    governance logic. It only orchestrates decision_engine, mutation_engine,
    replay_engine, counterfactual_engine, diff_engine, causal_engine and
    governance_engine, each of which stays the single source of truth for
    its own formula.
  - Mutation types that would require inventing a hypothetical new value
    that is not present anywhere in the historical record (CHANGE_POLICY,
    CHANGE_MODEL, CHANGE_THRESHOLD, ADD_EVIDENCE, MODIFY_EVIDENCE,
    MODIFY_TOOL_RESULT, CHANGE_INPUT) are NOT auto-generated here. Auto-
    generating them would mean fabricating an experiment parameter (e.g.
    "what if the threshold were 0.6?") with no basis in the recorded
    context. They remain available as *manual* counterfactuals via the
    existing /decisions/{id}/counterfactual endpoint; the sweep instead
    reports them as unsupported-for-auto-sweep, with the reason, so nothing
    is silently omitted.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone

from app.domain.enums import MutationType
from app.domain.models import Decision, DecisionContext
from app.engines import causal_engine, governance_engine
from app.engines.counterfactual_engine import CounterfactualResult, run_counterfactual
from app.engines.diff_engine import decision_sensitivity
from app.engines.mutation_engine import Mutation, apply_mutation

# Mutation types that CAN be auto-generated without fabricating a value:
# removing/disabling something that already exists in the recorded context.
_AUTO_GENERATABLE = (MutationType.REMOVE_EVIDENCE, MutationType.REMOVE_TOOL_RESULT, MutationType.DISABLE_CONTROL)

_UNSUPPORTED_REASONS: dict[MutationType, str] = {
    MutationType.CHANGE_POLICY: "Requires a hypothetical replacement PolicyVersion not present in the historical record.",
    MutationType.CHANGE_MODEL: "Requires a hypothetical replacement ModelVersion not present in the historical record.",
    MutationType.CHANGE_THRESHOLD: "Requires an arbitrary new threshold value; no canonical value to test without fabricating one.",
    MutationType.ADD_EVIDENCE: "Requires fabricating evidence that was never recorded for this decision.",
    MutationType.MODIFY_EVIDENCE: "Requires an arbitrary replacement value for an existing evidence item.",
    MutationType.MODIFY_TOOL_RESULT: "Requires an arbitrary replacement tool output; no canonical alternative to test.",
    MutationType.CHANGE_INPUT: "Requires an arbitrary replacement input payload; no canonical alternative to test.",
}


@dataclass(frozen=True)
class ForensicExperiment:
    experiment_id: str
    decision_id: str
    variable: str
    variable_kind: str  # "evidence" | "tool_invocation" | "control"
    mutation_type: str
    mutation_summary: str
    baseline_outcome: str
    baseline_score: float
    counterfactual_outcome: str
    counterfactual_score: float
    score_delta: float
    diverged: bool
    causal_status: str
    causal_explanation: str
    replayability_status: str
    replayability_reasons: tuple[str, ...]
    sensitivity: float
    boundary: dict
    governance_impact: tuple[dict, ...]


@dataclass(frozen=True)
class ForensicSweepSummary:
    experiment_count: int
    decision_critical_count: int
    decision_irrelevant_count: int
    contributory_count: int
    non_replayable_count: int
    most_sensitive_variable: str | None
    divergence_ratio: float


@dataclass(frozen=True)
class ForensicSweepResult:
    sweep_id: str
    decision_id: str
    baseline_outcome: str
    baseline_score: float
    experiments: tuple[ForensicExperiment, ...]
    unsupported_mutation_types: tuple[dict, ...]
    summary: ForensicSweepSummary
    timestamp: datetime


def generate_mutations(context: DecisionContext, decision_id: str) -> list[Mutation]:
    """Pure function: same context + decision_id -> same mutation list, same order,
    every time. No randomness, no LLM, no I/O."""
    mutations: list[Mutation] = []
    seq = 0

    for ev in context.evidence:
        seq += 1
        mutations.append(Mutation(
            mutation_id=f"MUT-{decision_id}-{seq:03d}",
            type=MutationType.REMOVE_EVIDENCE,
            target=ev.evidence_id,
            before=f"present (value={ev.value}, weight={ev.weight})",
            after="removed",
            reason="Forensic sweep: single-variable test of evidence contribution.",
            actor="forensic-sweep",
        ))

    for tool in context.tool_invocations:
        seq += 1
        mutations.append(Mutation(
            mutation_id=f"MUT-{decision_id}-{seq:03d}",
            type=MutationType.REMOVE_TOOL_RESULT,
            target=tool.tool_id,
            before=f"present ({tool.tool_name})",
            after="removed",
            reason="Forensic sweep: single-variable test of tool-result contribution.",
            actor="forensic-sweep",
        ))

    for control in context.control_definitions:
        seq += 1
        mutations.append(Mutation(
            mutation_id=f"MUT-{decision_id}-{seq:03d}",
            type=MutationType.DISABLE_CONTROL,
            target=control.control_id,
            before=f"active ({control.name})",
            after="disabled",
            reason="Forensic sweep: single-variable test of control contribution.",
            actor="forensic-sweep",
        ))

    return mutations


def _variable_kind(mutation_type: MutationType) -> str:
    return {
        MutationType.REMOVE_EVIDENCE: "evidence",
        MutationType.REMOVE_TOOL_RESULT: "tool_invocation",
        MutationType.DISABLE_CONTROL: "control",
    }[mutation_type]


def _boundary(baseline_score: float, cf_score: float, block_threshold: float, review_threshold: float) -> dict:
    return {
        "baseline_margin_to_block_threshold": round(block_threshold - baseline_score, 4),
        "baseline_margin_to_review_threshold": round(review_threshold - baseline_score, 4),
        "counterfactual_margin_to_block_threshold": round(block_threshold - cf_score, 4),
        "counterfactual_margin_to_review_threshold": round(review_threshold - cf_score, 4),
        "crossed_block_threshold": (baseline_score >= block_threshold) != (cf_score >= block_threshold),
        "crossed_review_threshold": (baseline_score >= review_threshold) != (cf_score >= review_threshold),
        "direction": "decrease" if cf_score < baseline_score else ("increase" if cf_score > baseline_score else "none"),
    }


def _governance_impact(decision: Decision, mutated_context: DecisionContext, cf_score: float, approved_model_ids: set[str] | None) -> tuple[dict, ...]:
    before = governance_engine.evaluate_controls(decision, approved_model_ids)
    mutated_view = replace(decision, context=mutated_context, risk_score=cf_score)
    after = governance_engine.evaluate_controls(mutated_view, approved_model_ids)
    after_by_id = {f.control_id: f for f in after}
    impact = []
    for f_before in before:
        f_after = after_by_id.get(f_before.control_id)
        impact.append({
            "control_id": f_before.control_id,
            "control_name": f_before.control_name,
            "before_status": f_before.status.value,
            "after_status": f_after.status.value if f_after else "NOT_APPLICABLE",
            "changed": f_after is not None and f_before.status != f_after.status,
        })
    return tuple(impact)


def run_forensic_sweep(decision: Decision, approved_model_ids: set[str] | None = None, sweep_id: str = "") -> ForensicSweepResult:
    """Runs one single-variable counterfactual experiment per auto-generatable
    mutation, each starting fresh from decision.context (the frozen baseline).
    Never mutates decision or decision.context. Pure/in-memory: no per-
    experiment DB queries."""
    decision_id = decision.decision_id
    sweep_id = sweep_id or f"SWEEP-{decision_id}"
    context = decision.context
    policy = context.policy_version

    mutations = generate_mutations(context, decision_id)
    experiments: list[ForensicExperiment] = []

    for i, mutation in enumerate(mutations, start=1):
        experiment_id = f"{sweep_id}-{i:03d}"
        cf_result: CounterfactualResult = run_counterfactual(decision, [mutation], counterfactual_id=f"CF-{experiment_id}")
        finding = causal_engine.analyze(cf_result)
        baseline_score = cf_result.original_replay.score
        cf_score = cf_result.counterfactual_replay.score
        sensitivity = decision_sensitivity(baseline_score, cf_score, policy.block_threshold)
        mutated_context = apply_mutation(context, mutation)
        governance_impact = _governance_impact(decision, mutated_context, cf_score, approved_model_ids)

        experiments.append(ForensicExperiment(
            experiment_id=experiment_id,
            decision_id=decision_id,
            variable=mutation.target,
            variable_kind=_variable_kind(mutation.type),
            mutation_type=mutation.type.value,
            mutation_summary=f"{mutation.type.value} on {mutation.target}",
            baseline_outcome=cf_result.original_replay.outcome.value,
            baseline_score=round(baseline_score, 4),
            counterfactual_outcome=cf_result.counterfactual_replay.outcome.value,
            counterfactual_score=round(cf_score, 4),
            score_delta=cf_result.diff.score_delta,
            diverged=cf_result.diff.diverged,
            causal_status=finding.status.value,
            causal_explanation=finding.explanation,
            replayability_status=cf_result.counterfactual_replay.replayability.status.value,
            replayability_reasons=tuple(r.value for r in cf_result.counterfactual_replay.replayability.reasons),
            sensitivity=sensitivity,
            boundary=_boundary(baseline_score, cf_score, policy.block_threshold, policy.review_threshold),
            governance_impact=governance_impact,
        ))

    unsupported = tuple(
        {"mutation_type": mt.value, "reason": reason}
        for mt, reason in _UNSUPPORTED_REASONS.items()
    )

    summary = _summarize(experiments)

    baseline_outcome = experiments[0].baseline_outcome if experiments else decision.final_outcome.value
    baseline_score = experiments[0].baseline_score if experiments else round(decision.risk_score, 4)

    return ForensicSweepResult(
        sweep_id=sweep_id,
        decision_id=decision_id,
        baseline_outcome=baseline_outcome,
        baseline_score=baseline_score,
        experiments=tuple(experiments),
        unsupported_mutation_types=unsupported,
        summary=summary,
        timestamp=datetime.now(timezone.utc),
    )


def _summarize(experiments: list[ForensicExperiment]) -> ForensicSweepSummary:
    count = len(experiments)
    critical = sum(1 for e in experiments if e.causal_status == "DECISION_CRITICAL")
    irrelevant = sum(1 for e in experiments if e.causal_status == "DECISION_IRRELEVANT")
    contributory = sum(1 for e in experiments if e.causal_status == "CONTRIBUTORY")
    non_replayable = sum(1 for e in experiments if e.causal_status == "NON_REPLAYABLE")
    diverged = sum(1 for e in experiments if e.diverged)
    most_sensitive = None
    if experiments:
        most_sensitive = max(experiments, key=lambda e: (e.sensitivity, e.variable)).variable
    return ForensicSweepSummary(
        experiment_count=count,
        decision_critical_count=critical,
        decision_irrelevant_count=irrelevant,
        contributory_count=contributory,
        non_replayable_count=non_replayable,
        most_sensitive_variable=most_sensitive,
        divergence_ratio=round(diverged / count, 4) if count else 0.0,
    )


def sweep_to_dict(result: ForensicSweepResult) -> dict:
    """JSON-serializable representation, used both for persistence (one atomic
    JSON blob, same pattern as DecisionContext -- see docs/architecture.md) and
    for the API response body."""
    return {
        "sweep_id": result.sweep_id,
        "decision_id": result.decision_id,
        "baseline_outcome": result.baseline_outcome,
        "baseline_score": result.baseline_score,
        "timestamp": result.timestamp.isoformat(),
        "experiments": [
            {
                "experiment_id": e.experiment_id,
                "decision_id": e.decision_id,
                "variable": e.variable,
                "variable_kind": e.variable_kind,
                "mutation_type": e.mutation_type,
                "mutation_summary": e.mutation_summary,
                "baseline_outcome": e.baseline_outcome,
                "baseline_score": e.baseline_score,
                "counterfactual_outcome": e.counterfactual_outcome,
                "counterfactual_score": e.counterfactual_score,
                "score_delta": e.score_delta,
                "diverged": e.diverged,
                "causal_status": e.causal_status,
                "causal_explanation": e.causal_explanation,
                "replayability_status": e.replayability_status,
                "replayability_reasons": list(e.replayability_reasons),
                "sensitivity": e.sensitivity,
                "boundary": e.boundary,
                "governance_impact": list(e.governance_impact),
            }
            for e in result.experiments
        ],
        "unsupported_mutation_types": list(result.unsupported_mutation_types),
        "summary": {
            "experiment_count": result.summary.experiment_count,
            "decision_critical_count": result.summary.decision_critical_count,
            "decision_irrelevant_count": result.summary.decision_irrelevant_count,
            "contributory_count": result.summary.contributory_count,
            "non_replayable_count": result.summary.non_replayable_count,
            "most_sensitive_variable": result.summary.most_sensitive_variable,
            "divergence_ratio": result.summary.divergence_ratio,
        },
    }
