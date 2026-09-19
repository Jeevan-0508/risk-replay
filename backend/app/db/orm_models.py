"""
backend/app/db/orm_models.py

Persistence schema. Design choice: the full DecisionContext (evidence, tools,
retrievals, model/policy snapshots) is stored as a JSON column rather than
fully normalized into per-entity tables. This is deliberate, not a shortcut
to avoid work -- documented in docs/architecture.md:
  - the context is always read/written as one atomic frozen unit (never
    partially updated), so JSON matches the actual access pattern
  - Postgres JSONB still supports indexing/querying into it if ever needed
  - it avoids ~8 extra join tables for a v1 system whose join complexity
    would outpace its query needs

Everything else (decisions, events, mutations, replays, counterfactuals,
incidents, policies, models) gets first-class indexed columns because those
ARE queried directly (by id, by time, by status).
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DecisionRecord(Base):
    __tablename__ = "decisions"

    decision_id: Mapped[str] = mapped_column(String, primary_key=True)
    system: Mapped[str] = mapped_column(String, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    context_json: Mapped[dict] = mapped_column(JSON)
    context_hash: Mapped[str] = mapped_column(String, index=True)
    decision: Mapped[str] = mapped_column(String, index=True)
    confidence: Mapped[float] = mapped_column(Float)
    risk_score: Mapped[float] = mapped_column(Float, index=True)
    outcome: Mapped[str] = mapped_column(String)
    controls_json: Mapped[list] = mapped_column(JSON, default=list)
    human_override_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String, ForeignKey("incidents.incident_id"), nullable=True, index=True)


class EventRecord(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    entity_id: Mapped[str] = mapped_column(String, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)


class MutationRecord(Base):
    __tablename__ = "mutations"

    mutation_id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String, ForeignKey("decisions.decision_id"), index=True)
    type: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    before: Mapped[str] = mapped_column(String)
    after: Mapped[str] = mapped_column(String)
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String, default="investigator")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)


class ReplayRecord(Base):
    __tablename__ = "replays"

    replay_id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String, ForeignKey("decisions.decision_id"), index=True)
    context_hash: Mapped[str] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    replayability_status: Mapped[str] = mapped_column(String)
    replayability_reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class CounterfactualRecord(Base):
    __tablename__ = "counterfactuals"

    counterfactual_id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String, ForeignKey("decisions.decision_id"), index=True)
    mutations_json: Mapped[list] = mapped_column(JSON, default=list)
    original_outcome: Mapped[str] = mapped_column(String)
    counterfactual_outcome: Mapped[str] = mapped_column(String)
    diverged: Mapped[bool] = mapped_column(Boolean, index=True)
    score_delta: Mapped[float] = mapped_column(Float)
    causal_status: Mapped[str] = mapped_column(String, index=True)
    causal_explanation: Mapped[str] = mapped_column(Text)
    is_multi_variable: Mapped[bool] = mapped_column(Boolean)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class IncidentRecord(Base):
    __tablename__ = "incidents"

    incident_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decision_ids_json: Mapped[list] = mapped_column(JSON, default=list)
    affected_evidence_kind: Mapped[str | None] = mapped_column(String, nullable=True)


class PolicyRecord(Base):
    __tablename__ = "policies"

    policy_id: Mapped[str] = mapped_column(String, primary_key=True)
    block_threshold: Mapped[float] = mapped_column(Float)
    review_threshold: Mapped[float] = mapped_column(Float)
    required_controls_json: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")


class ModelRecord(Base):
    __tablename__ = "models"

    model_id: Mapped[str] = mapped_column(String, primary_key=True)
    weights_json: Mapped[dict] = mapped_column(JSON, default=dict)
    base_rate: Mapped[float] = mapped_column(Float, default=0.0)
    description: Mapped[str] = mapped_column(Text, default="")


class ForensicSweepRecord(Base):
    __tablename__ = "forensic_sweeps"

    sweep_id: Mapped[str] = mapped_column(String, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String, ForeignKey("decisions.decision_id"), index=True)
    result_json: Mapped[dict] = mapped_column(JSON)
    experiment_count: Mapped[int] = mapped_column(Integer)
    decision_critical_count: Mapped[int] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
