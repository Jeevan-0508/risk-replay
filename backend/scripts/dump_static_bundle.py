"""
backend/scripts/dump_static_bundle.py

Dumps the full golden dataset into a single static JSON bundle that the
frontend can serve with zero backend (used for the GitHub Pages deploy).
Reuses the exact same engine functions the live API calls -- this is not a
separate mock, it's the same deterministic output, frozen to disk.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from app.golden_dataset import build_all_decisions
from app.engines.replay_engine import replay
from app.engines.risk_engine import assess_risk
from app.engines.governance_engine import evaluate_controls


def summary(d):
    return {
        "decision_id": d.decision_id, "system": d.system, "timestamp": d.timestamp.isoformat(),
        "model_id": d.context.model_version.model_id, "policy_id": d.context.policy_version.policy_id,
        "decision": d.decision.value, "final_outcome": d.final_outcome.value,
        "confidence": d.confidence, "risk_score": d.risk_score,
        "evidence_count": len(d.context.evidence),
        "incident_id": None,
    }


def detail(d, baseline):
    s = summary(d)
    return {
        **s,
        "evidence": [
            {**{k: v for k, v in asdict(e).items() if k != "payload"}, "classification": e.classification.value}
            for e in d.context.evidence
        ],
        "controls": [{"control_id": c.control_id, "status": c.status, "reason": c.reason} for c in d.controls],
        "tool_invocations": [
            {"tool_id": t.tool_id, "tool_name": t.tool_name, "output": t.output, "deterministic": t.deterministic}
            for t in d.context.tool_invocations
        ],
        "context_hash": d.context.context_hash(),
        "replayability_status": baseline.replayability.status.value,
        "replayability_reasons": [r.value for r in baseline.replayability.reasons],
    }


def lineage(d):
    ctx = d.context
    nodes = [{"id": ctx.input_snapshot.input_id, "type": "INPUT", "label": ctx.input_snapshot.system}]
    edges = []
    for r in ctx.retrievals:
        nodes.append({"id": r.retrieval_id, "type": "RETRIEVAL", "label": r.query})
        edges.append({"from": ctx.input_snapshot.input_id, "to": r.retrieval_id, "type": "USED_BY"})
    for e in ctx.evidence:
        nodes.append({"id": e.evidence_id, "type": "EVIDENCE", "label": f"{e.kind}={e.value}"})
        src = e.retrieved_by if e.retrieved_by else ctx.input_snapshot.input_id
        edges.append({"from": src, "to": e.evidence_id, "type": "DERIVED_FROM" if e.retrieved_by else "USED_BY"})
        edges.append({"from": e.evidence_id, "to": ctx.model_version.model_id, "type": "USED_BY"})
    nodes.append({"id": ctx.model_version.model_id, "type": "MODEL", "label": ctx.model_version.model_id})
    nodes.append({"id": ctx.policy_version.policy_id, "type": "POLICY", "label": ctx.policy_version.policy_id})
    edges.append({"from": ctx.model_version.model_id, "to": ctx.policy_version.policy_id, "type": "EVALUATED_BY"})
    for c in ctx.control_definitions:
        nodes.append({"id": c.control_id, "type": "CONTROL", "label": c.name})
        edges.append({"from": ctx.policy_version.policy_id, "to": c.control_id, "type": "GOVERNED_BY"})
    nodes.append({"id": d.decision_id, "type": "DECISION", "label": d.decision.value})
    edges.append({"from": ctx.policy_version.policy_id, "to": d.decision_id, "type": "RESULTED_IN"})
    return {"nodes": nodes, "edges": edges}


def risk_out(d):
    r = assess_risk(d)
    return {
        "decision_id": r.decision_id, "decision_risk": r.decision_risk,
        "evidence_completeness": r.evidence_completeness, "provenance_completeness": r.provenance_completeness,
        "control_coverage": r.control_coverage, "policy_violation_count": r.policy_violation_count,
        "replay_divergence": r.replay_divergence, "decision_sensitivity": r.decision_sensitivity,
        "risk_level": r.risk_level.value, "formulas": r.formulas,
    }


def governance_out(d):
    findings = evaluate_controls(d, approved_model_ids={"fraud-v3.2"})
    return [
        {"control_id": f.control_id, "control_name": f.control_name, "status": f.status.value,
         "reason": f.reason, "evidence": list(f.evidence)}
        for f in findings
    ]


def context_out(d):
    """Minimal frozen context needed for the client-side counterfactual engine."""
    ctx = d.context
    return {
        "evidence": [
            {"evidence_id": e.evidence_id, "kind": e.kind, "value": e.value, "weight": e.weight}
            for e in ctx.evidence
        ],
        "model_version": {
            "model_id": ctx.model_version.model_id,
            "weights": ctx.model_version.weights,
            "base_rate": ctx.model_version.base_rate,
        },
        "policy_version": {
            "policy_id": ctx.policy_version.policy_id,
            "block_threshold": ctx.policy_version.block_threshold,
            "review_threshold": ctx.policy_version.review_threshold,
        },
        "tool_invocations": [
            {"tool_id": t.tool_id, "tool_name": t.tool_name, "deterministic": t.deterministic}
            for t in ctx.tool_invocations
        ],
        "control_definitions": [
            {"control_id": c.control_id, "name": c.name, "rule": c.rule}
            for c in ctx.control_definitions
        ],
        "human_override": d.human_override is not None,
    }


def main():
    decisions = build_all_decisions()
    bundle = {"decisions": [], "details": {}, "lineage": {}, "risk": {}, "governance": {}, "contexts": {}}
    for d in decisions:
        baseline = replay(d)
        bundle["decisions"].append(summary(d))
        bundle["details"][d.decision_id] = detail(d, baseline)
        bundle["lineage"][d.decision_id] = lineage(d)
        bundle["risk"][d.decision_id] = risk_out(d)
        bundle["governance"][d.decision_id] = governance_out(d)
        bundle["contexts"][d.decision_id] = context_out(d)

    out_path = "../frontend/public/data/bundle.json"
    import os
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(bundle, f)
    print(f"wrote {len(decisions)} decisions to {out_path}")


if __name__ == "__main__":
    main()
