"""
backend/app/db/repository.py

Thin persistence-facing repository. Keeps SQLAlchemy specifics out of the API
layer and out of the engines (engines never import sqlalchemy).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.orm_models import (
    CounterfactualRecord,
    DecisionRecord,
    EventRecord,
    ForensicSweepRecord,
    IncidentRecord,
    ModelRecord,
    MutationRecord,
    PolicyRecord,
    ReplayRecord,
)
from app.db.serialization import decision_to_record_fields, record_to_decision
from app.domain.models import Decision
from app.engines.counterfactual_engine import CounterfactualResult
from app.engines.mutation_engine import Mutation
from app.engines.replay_engine import ReplayResult
from app.engines.sweep_engine import ForensicSweepResult, sweep_to_dict


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def record_event(db: Session, entity_id: str, event_type: str, payload: dict) -> None:
    db.add(EventRecord(
        event_id=new_id("EVT"), timestamp=datetime.now(timezone.utc),
        entity_id=entity_id, event_type=event_type, payload_json=payload, schema_version=1,
    ))


def save_decision(db: Session, decision: Decision) -> None:
    fields = decision_to_record_fields(decision)
    existing = db.get(DecisionRecord, decision.decision_id)
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        db.add(DecisionRecord(**fields))
    record_event(db, decision.decision_id, "DecisionCreated", {"decision": decision.decision.value})
    db.commit()


def get_decision(db: Session, decision_id: str) -> Decision | None:
    record = db.get(DecisionRecord, decision_id)
    return record_to_decision(record) if record else None


def list_decisions(db: Session, limit: int = 200) -> list[Decision]:
    records = db.execute(select(DecisionRecord).order_by(DecisionRecord.timestamp).limit(limit)).scalars().all()
    return [record_to_decision(r) for r in records]


def save_mutation(db: Session, decision_id: str, mutation: Mutation) -> None:
    db.add(MutationRecord(
        mutation_id=mutation.mutation_id, decision_id=decision_id, type=mutation.type.value,
        target=mutation.target, before=mutation.before, after=mutation.after,
        reason=mutation.reason, actor=mutation.actor, timestamp=mutation.timestamp,
        payload_json=mutation.payload,
    ))
    record_event(db, decision_id, "MutationApplied", {"mutation_id": mutation.mutation_id, "type": mutation.type.value})
    db.commit()


def save_replay(db: Session, result: ReplayResult) -> None:
    db.add(ReplayRecord(
        replay_id=result.replay_id, decision_id=result.decision_id, context_hash=result.context_hash,
        outcome=result.outcome.value, score=result.score,
        replayability_status=result.replayability.status.value,
        replayability_reasons_json=[r.value for r in result.replayability.reasons],
        timestamp=result.timestamp,
    ))
    record_event(db, result.decision_id, "ReplayCompleted", {"replay_id": result.replay_id, "outcome": result.outcome.value})
    db.commit()


def save_counterfactual(db: Session, result: CounterfactualResult, causal_status: str, causal_explanation: str) -> None:
    db.add(CounterfactualRecord(
        counterfactual_id=result.counterfactual_id, decision_id=result.decision_id,
        mutations_json=[
            {"mutation_id": m.mutation_id, "type": m.type.value, "target": m.target,
             "before": m.before, "after": m.after, "reason": m.reason, "actor": m.actor}
            for m in result.mutations
        ],
        original_outcome=result.original_replay.outcome.value,
        counterfactual_outcome=result.counterfactual_replay.outcome.value,
        diverged=result.diff.diverged, score_delta=result.diff.score_delta,
        causal_status=causal_status, causal_explanation=causal_explanation,
        is_multi_variable=result.is_multi_variable, timestamp=result.timestamp,
    ))
    if result.diff.diverged:
        record_event(db, result.decision_id, "DecisionDiverged", {
            "counterfactual_id": result.counterfactual_id,
            "original": result.original_replay.outcome.value,
            "counterfactual": result.counterfactual_replay.outcome.value,
        })
    db.commit()


def create_incident(db: Session, incident_id: str, title: str, description: str, decision_ids: list[str]) -> None:
    db.add(IncidentRecord(
        incident_id=incident_id, title=title, description=description,
        created_at=datetime.now(timezone.utc), decision_ids_json=decision_ids,
    ))
    for did in decision_ids:
        rec = db.get(DecisionRecord, did)
        if rec:
            rec.incident_id = incident_id
    record_event(db, incident_id, "IncidentCreated", {"decision_count": len(decision_ids)})
    db.commit()


def get_incident(db: Session, incident_id: str) -> IncidentRecord | None:
    return db.get(IncidentRecord, incident_id)


def list_events(db: Session, entity_id: str) -> list[EventRecord]:
    return db.execute(
        select(EventRecord).where(EventRecord.entity_id == entity_id).order_by(EventRecord.timestamp)
    ).scalars().all()


def upsert_policy(db: Session, policy) -> None:
    existing = db.get(PolicyRecord, policy.policy_id)
    fields = dict(
        block_threshold=policy.block_threshold, review_threshold=policy.review_threshold,
        required_controls_json=list(policy.required_controls), description=policy.description,
    )
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        db.add(PolicyRecord(policy_id=policy.policy_id, **fields))
    db.commit()


def upsert_model(db: Session, model) -> None:
    existing = db.get(ModelRecord, model.model_id)
    fields = dict(weights_json=model.weights, base_rate=model.base_rate, description=model.description)
    if existing:
        for k, v in fields.items():
            setattr(existing, k, v)
    else:
        db.add(ModelRecord(model_id=model.model_id, **fields))
    db.commit()


def list_policies(db: Session) -> list[PolicyRecord]:
    return db.execute(select(PolicyRecord)).scalars().all()


def list_models(db: Session) -> list[ModelRecord]:
    return db.execute(select(ModelRecord)).scalars().all()


def save_forensic_sweep(db: Session, result: ForensicSweepResult) -> None:
    db.add(ForensicSweepRecord(
        sweep_id=result.sweep_id, decision_id=result.decision_id,
        result_json=sweep_to_dict(result),
        experiment_count=result.summary.experiment_count,
        decision_critical_count=result.summary.decision_critical_count,
        timestamp=result.timestamp,
    ))
    record_event(db, result.decision_id, "ForensicSweepCompleted", {
        "sweep_id": result.sweep_id, "experiment_count": result.summary.experiment_count,
        "decision_critical_count": result.summary.decision_critical_count,
    })
    db.commit()


def get_forensic_sweep(db: Session, sweep_id: str) -> ForensicSweepRecord | None:
    return db.get(ForensicSweepRecord, sweep_id)


def list_forensic_sweeps(db: Session, decision_id: str) -> list[ForensicSweepRecord]:
    return db.execute(
        select(ForensicSweepRecord).where(ForensicSweepRecord.decision_id == decision_id).order_by(ForensicSweepRecord.timestamp)
    ).scalars().all()
