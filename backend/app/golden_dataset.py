"""
backend/app/golden_dataset.py

Synthetic golden dataset for RISK//REPLAY. ALL DATA HERE IS FICTIONAL AND
GENERATED FOR DEMONSTRATION. No real personal data, no real transactions.

Scenario: DEC-001, a fraud-engine decision that BLOCKED a transaction based on
four evidence items. This is the scenario the README's headline demo walks
through: remove evidence E3, replay, watch BLOCK -> ALLOW.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import DecisionOutcome, EvidenceClassification, GovernanceStatus
from app.domain.models import (
    ControlDefinition,
    ControlEvaluation,
    Decision,
    DecisionContext,
    Evidence,
    InputSnapshot,
    ModelVersion,
    PolicyVersion,
    Retrieval,
    ToolInvocation,
)
from app.engines.decision_engine import decide
from app.engines.governance_engine import evaluate_controls, to_control_evaluations


def build_fraud_v32() -> ModelVersion:
    return ModelVersion(
        model_id="fraud-v3.2",
        base_rate=0.05,
        weights={
            "velocity_signal": 0.25,
            "device_mismatch": 0.20,
            "identity_risk": 0.30,
            "payment_history_risk": 0.22,
        },
        description="Transparent weighted-sum fraud scoring model (demo).",
    )


def build_policy_17() -> PolicyVersion:
    return PolicyVersion(
        policy_id="policy-17",
        block_threshold=0.82,
        review_threshold=0.55,
        required_controls=("C-17", "C-08"),
        description="Fraud block/review policy, v17 (demo).",
    )


def build_policy_18() -> PolicyVersion:
    """A stricter successor policy used in the policy-impact-replay demo."""
    return PolicyVersion(
        policy_id="policy-18",
        block_threshold=0.75,
        review_threshold=0.45,
        required_controls=("C-17", "C-08"),
        description="Fraud block/review policy, v18 -- lowered thresholds (demo).",
    )


def build_dec_001() -> Decision:
    model = build_fraud_v32()
    policy = build_policy_17()

    input_snapshot = InputSnapshot(
        input_id="IN-001",
        system="fraud-engine",
        payload={"transaction_id": "TXN-88213", "amount": 1420.00, "currency": "USD"},
    ).with_hash()

    retrieval_r1 = Retrieval(
        retrieval_id="R1", query="payment_history:acct-4471", source="payment-history",
        result_ids=("E2",),
    )

    evidence = (
        Evidence(evidence_id="E1", source="risk-engine", kind="velocity_signal",
                  value=0.9, weight=0.25, classification=EvidenceClassification.INTERNAL).with_hash(),
        Evidence(evidence_id="E2", source="payment-history", kind="payment_history_risk",
                  value=0.7, weight=0.22, classification=EvidenceClassification.INTERNAL,
                  retrieved_by="R1").with_hash(),
        Evidence(evidence_id="E3", source="identity-service", kind="identity_risk",
                  value=0.95, weight=0.30, classification=EvidenceClassification.SENSITIVE).with_hash(),
        Evidence(evidence_id="E4", source="risk-engine", kind="device_mismatch",
                  value=0.6, weight=0.20, classification=EvidenceClassification.INTERNAL).with_hash(),
    )

    tool_invocations = (
        ToolInvocation(tool_id="T1", tool_name="risk-engine", inputs={"acct": "4471"},
                        output={"velocity_signal": 0.9}, deterministic=True),
        ToolInvocation(tool_id="T2", tool_name="identity-service", inputs={"acct": "4471"},
                        output={"identity_risk": 0.95}, deterministic=True),
        ToolInvocation(tool_id="T3", tool_name="payment-history", inputs={"acct": "4471"},
                        output={"payment_history_risk": 0.7}, deterministic=True),
    )

    controls = (
        ControlDefinition(control_id="C-17", name="Human Oversight",
                           description="", rule="human_review_above_review_threshold"),
        ControlDefinition(control_id="C-08", name="Approved Model Version",
                           description="", rule="approved_model_version"),
    )

    context = DecisionContext(
        input_snapshot=input_snapshot,
        evidence=evidence,
        retrievals=(retrieval_r1,),
        model_version=model,
        policy_version=policy,
        tool_invocations=tool_invocations,
        control_definitions=controls,
    )

    outcome, score, breakdown = decide(context)

    decision = Decision(
        decision_id="DEC-001",
        system="fraud-engine",
        timestamp=datetime(2026, 9, 10, 9, 31, 0, tzinfo=timezone.utc),
        context=context,
        decision=outcome,
        confidence=round(0.5 + score / 2, 4),
        risk_score=score,
        outcome=f"TRANSACTION_{'BLOCKED' if outcome == DecisionOutcome.BLOCK else outcome.value}",
    )

    findings = evaluate_controls(decision, approved_model_ids={"fraud-v3.2"})
    decision = decision.__class__(**{**decision.__dict__, "controls": to_control_evaluations(findings)})
    return decision


def build_all_decisions() -> list[Decision]:
    """A small spread of synthetic decisions across scenarios, used for the
    policy-impact and blast-radius demos. All fictional."""
    decisions = [build_dec_001()]

    model = build_fraud_v32()
    policy = build_policy_17()
    controls = (
        ControlDefinition(control_id="C-17", name="Human Oversight",
                           description="", rule="human_review_above_review_threshold"),
        ControlDefinition(control_id="C-08", name="Approved Model Version",
                           description="", rule="approved_model_version"),
    )

    import random
    rng = random.Random(42)
    for i in range(2, 41):
        vals = {k: round(rng.uniform(0.1, 0.95), 2) for k in model.weights}
        evidence = tuple(
            Evidence(evidence_id=f"E{i}-{j}", source="risk-engine", kind=kind,
                      value=v, weight=model.weights[kind]).with_hash()
            for j, (kind, v) in enumerate(vals.items())
        )
        input_snapshot = InputSnapshot(
            input_id=f"IN-{i:03d}", system="fraud-engine",
            payload={"transaction_id": f"TXN-{80000+i}", "amount": round(rng.uniform(20, 5000), 2)},
        ).with_hash()
        context = DecisionContext(
            input_snapshot=input_snapshot, evidence=evidence, retrievals=(),
            model_version=model, policy_version=policy, tool_invocations=(),
            control_definitions=controls,
        )
        outcome, score, _ = decide(context)
        decision = Decision(
            decision_id=f"DEC-{i:03d}", system="fraud-engine",
            timestamp=datetime(2026, 9, 10, 9, 0, 0, tzinfo=timezone.utc) + __import__('datetime').timedelta(minutes=31 + i),
            context=context, decision=outcome, confidence=round(0.5 + score / 2, 4),
            risk_score=score, outcome=f"TRANSACTION_{outcome.value}",
        )
        findings = evaluate_controls(decision, approved_model_ids={"fraud-v3.2"})
        decision = decision.__class__(**{**decision.__dict__, "controls": to_control_evaluations(findings)})
        decisions.append(decision)

    return decisions
