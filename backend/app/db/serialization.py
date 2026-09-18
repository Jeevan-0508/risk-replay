"""
backend/app/db/serialization.py

Converts between the frozen domain dataclasses (app.domain.models) and plain
JSON-safe dicts for storage in DecisionRecord.context_json. This is the one
place that knows how to round-trip a DecisionContext.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from app.domain.enums import EvidenceClassification
from app.domain.models import (
    ControlDefinition,
    ControlEvaluation,
    Decision,
    DecisionContext,
    Evidence,
    HumanOverride,
    InputSnapshot,
    ModelVersion,
    PolicyVersion,
    Retrieval,
    ToolInvocation,
)


def _dt(v) -> str:
    return v.isoformat() if isinstance(v, datetime) else v


def context_to_dict(ctx: DecisionContext) -> dict:
    d = asdict(ctx)
    d["input_snapshot"] = {**d["input_snapshot"]}
    for ev in d["evidence"]:
        ev["classification"] = ev["classification"].value if hasattr(ev["classification"], "value") else ev["classification"]
    for r in d["retrievals"]:
        r["timestamp"] = _dt(r["timestamp"])
    for t in d["tool_invocations"]:
        t["timestamp"] = _dt(t["timestamp"])
    return d


def context_from_dict(d: dict) -> DecisionContext:
    input_snapshot = InputSnapshot(**d["input_snapshot"])
    evidence = tuple(
        Evidence(**{**e, "classification": EvidenceClassification(e["classification"])})
        for e in d["evidence"]
    )
    retrievals = tuple(
        Retrieval(**{**r, "timestamp": datetime.fromisoformat(r["timestamp"]), "result_ids": tuple(r["result_ids"])})
        for r in d["retrievals"]
    )
    tool_invocations = tuple(
        ToolInvocation(**{**t, "timestamp": datetime.fromisoformat(t["timestamp"])})
        for t in d["tool_invocations"]
    )
    model_version = ModelVersion(**d["model_version"])
    policy_version = PolicyVersion(**{**d["policy_version"], "required_controls": tuple(d["policy_version"]["required_controls"])})
    control_definitions = tuple(ControlDefinition(**c) for c in d.get("control_definitions", []))
    return DecisionContext(
        input_snapshot=input_snapshot, evidence=evidence, retrievals=retrievals,
        model_version=model_version, policy_version=policy_version,
        tool_invocations=tool_invocations, control_definitions=control_definitions,
    )


def decision_to_record_fields(decision: Decision) -> dict:
    return dict(
        decision_id=decision.decision_id,
        system=decision.system,
        timestamp=decision.timestamp,
        context_json=context_to_dict(decision.context),
        context_hash=decision.context.context_hash(),
        decision=decision.decision.value,
        confidence=decision.confidence,
        risk_score=decision.risk_score,
        outcome=decision.outcome,
        controls_json=[asdict(c) for c in decision.controls],
        human_override_json=(
            {**asdict(decision.human_override),
             "timestamp": _dt(decision.human_override.timestamp),
             "original_decision": decision.human_override.original_decision.value,
             "overridden_decision": decision.human_override.overridden_decision.value}
            if decision.human_override else None
        ),
    )


def record_to_decision(record) -> Decision:
    from app.domain.enums import DecisionOutcome
    ctx = context_from_dict(record.context_json)
    human_override = None
    if record.human_override_json:
        ho = record.human_override_json
        human_override = HumanOverride(
            override_id=ho["override_id"], actor=ho["actor"],
            original_decision=DecisionOutcome(ho["original_decision"]),
            overridden_decision=DecisionOutcome(ho["overridden_decision"]),
            reason=ho["reason"], timestamp=datetime.fromisoformat(ho["timestamp"]),
        )
    controls = tuple(ControlEvaluation(**c) for c in record.controls_json)
    return Decision(
        decision_id=record.decision_id, system=record.system, timestamp=record.timestamp,
        context=ctx, decision=DecisionOutcome(record.decision), confidence=record.confidence,
        risk_score=record.risk_score, controls=controls, human_override=human_override,
        outcome=record.outcome,
    )
