"""backend/app/api/schemas.py -- Pydantic request/response contracts."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceOut(BaseModel):
    evidence_id: str
    source: str
    kind: str
    value: float
    weight: float
    classification: str
    retrieved_by: str | None = None
    content_hash: str


class DecisionSummaryOut(BaseModel):
    decision_id: str
    system: str
    timestamp: datetime
    model_id: str
    policy_id: str
    decision: str
    final_outcome: str
    confidence: float
    risk_score: float
    evidence_count: int
    incident_id: str | None = None


class DecisionDetailOut(DecisionSummaryOut):
    evidence: list[EvidenceOut]
    controls: list[dict]
    tool_invocations: list[dict]
    context_hash: str
    replayability_status: str
    replayability_reasons: list[str]


class MutationIn(BaseModel):
    type: str
    target: str
    reason: str
    actor: str = "investigator"
    payload: dict = Field(default_factory=dict)


class CounterfactualIn(BaseModel):
    mutations: list[MutationIn]


class ReplayOut(BaseModel):
    replay_id: str
    decision_id: str
    outcome: str
    score: float
    replayability_status: str
    replayability_reasons: list[str]


class CounterfactualOut(BaseModel):
    counterfactual_id: str
    decision_id: str
    original_outcome: str
    original_score: float
    counterfactual_outcome: str
    counterfactual_score: float
    diverged: bool
    score_delta: float
    causal_status: str
    causal_explanation: str
    is_multi_variable: bool
    diff_fields: list[dict]


class RiskAssessmentOut(BaseModel):
    decision_id: str
    decision_risk: float
    evidence_completeness: float
    provenance_completeness: float
    control_coverage: float
    policy_violation_count: int
    replay_divergence: float | None
    decision_sensitivity: float | None
    risk_level: str
    formulas: dict


class GovernanceFindingOut(BaseModel):
    control_id: str
    control_name: str
    status: str
    reason: str
    evidence: list[str]


class IncidentIn(BaseModel):
    title: str
    description: str = ""
    decision_ids: list[str]
    affected_evidence_kind: str | None = None  # e.g. "identity_risk" -- the shared
    # evidence dimension suspected compromised across every decision in this incident,
    # used to drive a real per-decision counterfactual in the blast-radius engine.


class PolicyIn(BaseModel):
    policy_id: str
    block_threshold: float
    review_threshold: float
    required_controls: list[str] = Field(default_factory=list)
    description: str = ""


class ModelIn(BaseModel):
    model_id: str
    weights: dict[str, float]
    base_rate: float = 0.0
    description: str = ""


class ForensicSweepIn(BaseModel):
    approved_model: str = "fraud-v3.2"
