"""
backend/app/engines/incident_engine.py

INCIDENT BLAST-RADIUS FORENSICS: given a set of decisions grouped under an
incident, and (optionally) a specific evidence "kind" suspected of being
compromised, compute the real, replay-derived impact across all of them.

This does not invent a root cause. It reports a "common replay dependency"
-- the shared evidence kind / source / model / policy chain that, when
removed via a real counterfactual on every affected decision, changes the
outcome of some subset of them. That is a fact about the replay model, not
a claim about what actually happened in the real world -- see
docs/methodology.md and the explicit wording rule below.

Every count here is computed by calling replay_engine and
counterfactual_engine per decision, exactly the same way sweep_engine does
for a single decision. Nothing is aggregated from a fabricated or cached
percentage.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.domain.enums import MutationType, ReplayabilityStatus
from app.domain.models import Decision
from app.engines.counterfactual_engine import run_counterfactual
from app.engines.mutation_engine import Mutation
from app.engines.replay_engine import replay


@dataclass(frozen=True)
class DecisionImpact:
    decision_id: str
    replayability_status: str
    has_dependency: bool          # does this decision contain evidence of the affected kind?
    evidence_id: str | None       # which evidence item, if has_dependency
    baseline_outcome: str | None
    counterfactual_outcome: str | None
    changed: bool                 # outcome flips if that evidence is removed

    def to_dict(self) -> dict:
        return {
            "decision_id": self.decision_id,
            "replayability_status": self.replayability_status,
            "has_dependency": self.has_dependency,
            "evidence_id": self.evidence_id,
            "baseline_outcome": self.baseline_outcome,
            "counterfactual_outcome": self.counterfactual_outcome,
            "changed": self.changed,
        }


@dataclass(frozen=True)
class BlastRadiusReport:
    incident_id: str
    affected_evidence_kind: str | None
    affected_decisions: int
    replayable_count: int
    partially_replayable_count: int
    non_replayable_count: int
    decisions_with_dependency: int
    decisions_changed: int
    decisions_unchanged: int
    affected_policies: tuple[str, ...]
    affected_models: tuple[str, ...]
    affected_evidence_sources: tuple[str, ...]
    affected_controls: tuple[str, ...]
    common_replay_dependency: dict | None
    decision_impacts: tuple[DecisionImpact, ...]
    timestamp: datetime

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "affected_evidence_kind": self.affected_evidence_kind,
            "affected_decisions": self.affected_decisions,
            "replayable_count": self.replayable_count,
            "partially_replayable_count": self.partially_replayable_count,
            "non_replayable_count": self.non_replayable_count,
            "decisions_with_dependency": self.decisions_with_dependency,
            "decisions_changed": self.decisions_changed,
            "decisions_unchanged": self.decisions_unchanged,
            "affected_policies": list(self.affected_policies),
            "affected_models": list(self.affected_models),
            "affected_evidence_sources": list(self.affected_evidence_sources),
            "affected_controls": list(self.affected_controls),
            "common_replay_dependency": self.common_replay_dependency,
            "decision_impacts": [d.to_dict() for d in self.decision_impacts],
            "timestamp": self.timestamp.isoformat(),
        }


def analyze_blast_radius(
    incident_id: str,
    decisions: list[Decision],
    affected_evidence_kind: str | None = None,
) -> BlastRadiusReport:
    """Compute real, replay-derived incident impact.

    If `affected_evidence_kind` is None, this reports the replayability
    breakdown and affected policy/model/source/control sets only --
    `decisions_with_dependency`/`decisions_changed` stay 0 and
    `common_replay_dependency` stays None, honestly reflecting that no
    specific suspected variable was supplied to test.
    """
    replayable = 0
    partial = 0
    non_replayable = 0
    policies: set[str] = set()
    models: set[str] = set()
    sources: set[str] = set()
    controls: set[str] = set()
    impacts: list[DecisionImpact] = []

    for d in decisions:
        result = replay(d)
        status = result.replayability.status
        if status == ReplayabilityStatus.REPLAYABLE:
            replayable += 1
        elif status == ReplayabilityStatus.PARTIALLY_REPLAYABLE:
            partial += 1
        else:
            non_replayable += 1

        policies.add(d.context.policy_version.policy_id)
        models.add(d.context.model_version.model_id)
        sources.update(e.source for e in d.context.evidence)
        controls.update(c.control_id for c in d.controls)

        has_dependency = False
        evidence_id = None
        baseline_outcome = None
        counterfactual_outcome = None
        changed = False

        if affected_evidence_kind is not None:
            match = next((e for e in d.context.evidence if e.kind == affected_evidence_kind), None)
            if match is not None:
                has_dependency = True
                evidence_id = match.evidence_id
                mutation = Mutation(
                    mutation_id=f"BLAST-{incident_id}-{d.decision_id}",
                    type=MutationType.REMOVE_EVIDENCE, target=match.evidence_id,
                    before=str(match.value), after="removed",
                    reason=f"Incident {incident_id} blast-radius probe on evidence kind '{affected_evidence_kind}'.",
                )
                cf = run_counterfactual(d, [mutation])
                baseline_outcome = cf.original_replay.outcome.value
                counterfactual_outcome = cf.counterfactual_replay.outcome.value
                changed = cf.diff.diverged

        impacts.append(DecisionImpact(
            decision_id=d.decision_id, replayability_status=status.value,
            has_dependency=has_dependency, evidence_id=evidence_id,
            baseline_outcome=baseline_outcome, counterfactual_outcome=counterfactual_outcome,
            changed=changed,
        ))

    decisions_with_dependency = sum(1 for i in impacts if i.has_dependency)
    decisions_changed = sum(1 for i in impacts if i.changed)
    decisions_unchanged = decisions_with_dependency - decisions_changed

    common_dependency = None
    if affected_evidence_kind is not None and decisions_with_dependency > 0:
        dependent = [d for d, i in zip(decisions, impacts) if i.has_dependency]
        example_evidence = next(e for e in dependent[0].context.evidence if e.kind == affected_evidence_kind)
        common_dependency = {
            "evidence_kind": affected_evidence_kind,
            "evidence_source": example_evidence.source,
            "model": dependent[0].context.model_version.model_id,
            "policy": dependent[0].context.policy_version.policy_id,
            "decisions_changed": decisions_changed,
            "label": (
                f"{affected_evidence_kind} -> {example_evidence.source} -> "
                f"{dependent[0].context.model_version.model_id} -> {dependent[0].context.policy_version.policy_id} "
                f"-> {decisions_changed} changed decisions"
            ),
            "note": "Common replay dependency: a shared variable whose removal changes these "
                    "decisions' outcomes under replay. This is not asserted as the real-world root cause.",
        }

    return BlastRadiusReport(
        incident_id=incident_id,
        affected_evidence_kind=affected_evidence_kind,
        affected_decisions=len(decisions),
        replayable_count=replayable,
        partially_replayable_count=partial,
        non_replayable_count=non_replayable,
        decisions_with_dependency=decisions_with_dependency,
        decisions_changed=decisions_changed,
        decisions_unchanged=decisions_unchanged,
        affected_policies=tuple(sorted(policies)),
        affected_models=tuple(sorted(models)),
        affected_evidence_sources=tuple(sorted(sources)),
        affected_controls=tuple(sorted(controls)),
        common_replay_dependency=common_dependency,
        decision_impacts=tuple(impacts),
        timestamp=datetime.now(timezone.utc),
    )
