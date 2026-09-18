"""
backend/app/domain/models.py

Core domain model for RISK//REPLAY.

Design rule: these are plain, hashable, serializable dataclasses that represent
the FULL historical state of a decision. Nothing in here reaches out to a live
system at replay time -- a Decision's context is a frozen snapshot.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.domain.enums import DecisionOutcome, EvidenceClassification


def now() -> datetime:
    return datetime.now(timezone.utc)


def stable_hash(payload: Any) -> str:
    """Deterministic content hash used for provenance, not for security guarantees.

    This proves 'this exact byte content was recorded at this ID', nothing more.
    It does NOT prove the content is true, and it does NOT prove nobody could have
    forged it before ingestion -- see docs/security.md.
    """
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


@dataclass(frozen=True)
class Evidence:
    """A single piece of evidence used by a decision, frozen at ingestion time."""
    evidence_id: str
    source: str                     # e.g. "identity-service", "payment-history"
    kind: str                       # e.g. "risk_signal", "identity_check"
    value: float                    # normalized 0..1 signal strength used by the rule engine
    weight: float                   # weight assigned by the model version at decision time
    classification: EvidenceClassification = EvidenceClassification.INTERNAL
    retrieved_by: str | None = None  # retrieval id, if evidence came via a retrieval step
    payload: dict = field(default_factory=dict)
    content_hash: str = ""

    def with_hash(self) -> "Evidence":
        h = stable_hash({
            "evidence_id": self.evidence_id, "source": self.source, "kind": self.kind,
            "value": self.value, "weight": self.weight, "payload": self.payload,
        })
        return Evidence(**{**self.__dict__, "content_hash": h})


@dataclass(frozen=True)
class Retrieval:
    retrieval_id: str
    query: str
    source: str
    result_ids: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=now)


@dataclass(frozen=True)
class ToolInvocation:
    tool_id: str
    tool_name: str
    inputs: dict = field(default_factory=dict)
    output: dict = field(default_factory=dict)
    deterministic: bool = True      # if False, decision is at most PARTIALLY_REPLAYABLE
    timestamp: datetime = field(default_factory=now)


@dataclass(frozen=True)
class ModelVersion:
    model_id: str          # e.g. "fraud-v3.2"
    weights: dict          # evidence "kind" -> weight, the deterministic scoring rule
    base_rate: float = 0.0
    description: str = ""


@dataclass(frozen=True)
class PolicyVersion:
    policy_id: str          # e.g. "policy-17"
    block_threshold: float
    review_threshold: float
    required_controls: tuple[str, ...] = ()
    description: str = ""


@dataclass(frozen=True)
class ControlDefinition:
    control_id: str          # e.g. "C-17"
    name: str
    description: str
    rule: str                # symbolic rule name evaluated by governance engine


@dataclass(frozen=True)
class ControlEvaluation:
    control_id: str
    status: str               # GovernanceStatus value, computed, not asserted
    reason: str


@dataclass(frozen=True)
class HumanOverride:
    override_id: str
    actor: str
    original_decision: DecisionOutcome
    overridden_decision: DecisionOutcome
    reason: str
    timestamp: datetime = field(default_factory=now)


@dataclass(frozen=True)
class InputSnapshot:
    input_id: str
    system: str
    payload: dict = field(default_factory=dict)
    content_hash: str = ""

    def with_hash(self) -> "InputSnapshot":
        h = stable_hash(self.payload)
        return InputSnapshot(**{**self.__dict__, "content_hash": h})


@dataclass(frozen=True)
class DecisionContext:
    """The full frozen state a decision was made from. This is what gets replayed."""
    input_snapshot: InputSnapshot
    evidence: tuple[Evidence, ...]
    retrievals: tuple[Retrieval, ...]
    model_version: ModelVersion
    policy_version: PolicyVersion
    tool_invocations: tuple[ToolInvocation, ...]
    control_definitions: tuple[ControlDefinition, ...] = ()

    def context_hash(self) -> str:
        return stable_hash({
            "input": self.input_snapshot.content_hash,
            "evidence": sorted(e.evidence_id + e.content_hash for e in self.evidence),
            "model": self.model_version.model_id,
            "policy": self.policy_version.policy_id,
            "tools": sorted(t.tool_id for t in self.tool_invocations),
        })


@dataclass(frozen=True)
class Decision:
    """A persisted, historical AI-assisted decision. Immutable once recorded."""
    decision_id: str
    system: str
    timestamp: datetime
    context: DecisionContext
    decision: DecisionOutcome
    confidence: float
    risk_score: float
    controls: tuple[ControlEvaluation, ...] = ()
    human_override: HumanOverride | None = None
    outcome: str = ""

    @property
    def final_outcome(self) -> DecisionOutcome:
        if self.human_override:
            return self.human_override.overridden_decision
        return self.decision
