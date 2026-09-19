"""
backend/app/api/main.py

RISK//REPLAY API server. Every route below calls into a real engine or the
repository -- there are no hardcoded/fake responses. If a capability isn't
built yet, the route does not exist rather than returning fabricated data.
"""
from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.db.database import get_db, init_db
from app.db import repository as repo
from app.domain.enums import MutationType
from app.domain.models import ModelVersion, PolicyVersion
from app.engines.causal_engine import analyze
from app.engines.counterfactual_engine import run_counterfactual
from app.engines.governance_engine import evaluate_controls
from app.engines.mutation_engine import Mutation
from app.engines.replay_engine import replay
from app.engines.risk_engine import assess_risk
from app.engines.sweep_engine import run_forensic_sweep, sweep_to_dict
from app.engines import boundary_engine, dna_engine, integrity_engine, incident_engine
from app.api.schemas import (
    CounterfactualIn,
    CounterfactualOut,
    DecisionDetailOut,
    DecisionSummaryOut,
    ForensicSweepIn,
    GovernanceFindingOut,
    IncidentIn,
    ModelIn,
    PolicyIn,
    ReplayOut,
    RiskAssessmentOut,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("riskreplay")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="RISK//REPLAY API",
    description="AI Decision Forensics & Counterfactual Replay Engine",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _summary(decision) -> DecisionSummaryOut:
    return DecisionSummaryOut(
        decision_id=decision.decision_id, system=decision.system, timestamp=decision.timestamp,
        model_id=decision.context.model_version.model_id, policy_id=decision.context.policy_version.policy_id,
        decision=decision.decision.value, final_outcome=decision.final_outcome.value,
        confidence=decision.confidence, risk_score=decision.risk_score,
        evidence_count=len(decision.context.evidence),
    )


@app.get("/health")
def health():
    return {"status": "ok", "service": "risk-replay-api"}


@app.get("/decisions", response_model=list[DecisionSummaryOut])
def list_decisions(db: Session = Depends(get_db)):
    return [_summary(d) for d in repo.list_decisions(db)]


@app.get("/decisions/{decision_id}", response_model=DecisionDetailOut)
def get_decision(decision_id: str, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    baseline = replay(decision)
    from dataclasses import asdict
    return DecisionDetailOut(
        **_summary(decision).model_dump(),
        evidence=[
            {**asdict(e), "classification": e.classification.value} for e in decision.context.evidence
        ],
        controls=[{"control_id": c.control_id, "status": c.status, "reason": c.reason} for c in decision.controls],
        tool_invocations=[
            {"tool_id": t.tool_id, "tool_name": t.tool_name, "output": t.output, "deterministic": t.deterministic}
            for t in decision.context.tool_invocations
        ],
        context_hash=decision.context.context_hash(),
        replayability_status=baseline.replayability.status.value,
        replayability_reasons=[r.value for r in baseline.replayability.reasons],
    )


@app.get("/decisions/{decision_id}/lineage")
def get_lineage(decision_id: str, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    ctx = decision.context
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
    nodes.append({"id": decision.decision_id, "type": "DECISION", "label": decision.decision.value})
    edges.append({"from": ctx.policy_version.policy_id, "to": decision.decision_id, "type": "RESULTED_IN"})
    return {"nodes": nodes, "edges": edges}


@app.post("/decisions/{decision_id}/replay", response_model=ReplayOut)
def replay_decision(decision_id: str, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    result = replay(decision)
    repo.save_replay(db, result)
    return ReplayOut(
        replay_id=result.replay_id, decision_id=result.decision_id, outcome=result.outcome.value,
        score=result.score, replayability_status=result.replayability.status.value,
        replayability_reasons=[r.value for r in result.replayability.reasons],
    )


@app.post("/decisions/{decision_id}/counterfactual", response_model=CounterfactualOut)
def counterfactual(decision_id: str, body: CounterfactualIn, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")

    mutations = []
    for m in body.mutations:
        try:
            mtype = MutationType(m.type)
        except ValueError:
            raise HTTPException(400, f"Unknown mutation type: {m.type}")
        mutation = Mutation(
            mutation_id=f"MUT-{uuid.uuid4().hex[:10]}", type=mtype, target=m.target,
            before="unknown", after="unknown", reason=m.reason, actor=m.actor, payload=m.payload,
        )
        mutations.append(mutation)
        repo.save_mutation(db, decision_id, mutation)

    try:
        result = run_counterfactual(decision, mutations)
    except Exception as exc:
        logger.exception("Counterfactual failed for %s", decision_id)
        raise HTTPException(400, str(exc))

    finding = analyze(result)
    repo.save_counterfactual(db, result, finding.status.value, finding.explanation)

    return CounterfactualOut(
        counterfactual_id=result.counterfactual_id, decision_id=decision_id,
        original_outcome=result.original_replay.outcome.value, original_score=result.original_replay.score,
        counterfactual_outcome=result.counterfactual_replay.outcome.value,
        counterfactual_score=result.counterfactual_replay.score,
        diverged=result.diff.diverged, score_delta=result.diff.score_delta,
        causal_status=finding.status.value, causal_explanation=finding.explanation,
        is_multi_variable=result.is_multi_variable, diff_fields=result.diff.as_table(),
    )


@app.post("/decisions/{decision_id}/forensic-sweep")
def forensic_sweep(decision_id: str, body: ForensicSweepIn = ForensicSweepIn(), db: Session = Depends(get_db)):
    """Runs the automatic single-variable Forensic Sweep (see docs/forensic-sweep.md):
    one deterministic counterfactual experiment per evidence item, tool invocation
    and control, each starting fresh from the decision's own recorded context.
    Every field in the response comes from the real engines -- nothing mocked."""
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    try:
        result = run_forensic_sweep(decision, approved_model_ids={body.approved_model})
    except Exception as exc:
        logger.exception("Forensic sweep failed for %s", decision_id)
        raise HTTPException(400, str(exc))
    repo.save_forensic_sweep(db, result)
    return sweep_to_dict(result)


@app.get("/decisions/{decision_id}/forensic-sweeps")
def list_forensic_sweeps(decision_id: str, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    records = repo.list_forensic_sweeps(db, decision_id)
    return [
        {"sweep_id": r.sweep_id, "decision_id": r.decision_id, "experiment_count": r.experiment_count,
         "decision_critical_count": r.decision_critical_count, "timestamp": r.timestamp}
        for r in records
    ]


@app.get("/decisions/{decision_id}/forensic-sweeps/{sweep_id}")
def get_forensic_sweep(decision_id: str, sweep_id: str, db: Session = Depends(get_db)):
    record = repo.get_forensic_sweep(db, sweep_id)
    if not record or record.decision_id != decision_id:
        raise HTTPException(404, f"Forensic sweep {sweep_id} not found for decision {decision_id}")
    return record.result_json


@app.get("/decisions/{decision_id}/boundary")
def get_boundary(decision_id: str, db: Session = Depends(get_db)):
    """Decision Boundary Analyzer: where this decision's score sits relative
    to its policy's block/review thresholds. Pure delegation to
    boundary_engine -- see docs/decision-boundary.md."""
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    policy = decision.context.policy_version
    profile = boundary_engine.analyze(decision.risk_score, policy.block_threshold, policy.review_threshold)
    return profile.to_dict()


@app.get("/decisions/{decision_id}/integrity")
def get_integrity(decision_id: str, db: Session = Depends(get_db)):
    """Replay Integrity: recomputes every content hash this system actually
    tracks (evidence, input snapshot, whole-context) and compares against
    what was persisted at save time. See docs/integrity.md for exactly what
    this does and does not guarantee."""
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    stored_hash = repo.get_stored_context_hash(db, decision_id)
    report = integrity_engine.verify_integrity(decision, stored_context_hash=stored_hash)
    return report.to_dict()


@app.get("/decisions/{decision_id}/dna")
def get_dna(decision_id: str, approved_model: str = "fraud-v3.2", db: Session = Depends(get_db)):
    """Decision DNA: a deterministic, human-readable forensic summary. Runs a
    fresh in-memory Forensic Sweep (pure, deterministic, no side effects --
    not persisted by this call) so decision_critical_variables and
    governance_affected_controls reflect real computed results, never a
    fabricated placeholder. See docs/decision-dna.md."""
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    baseline = replay(decision)
    sweep = run_forensic_sweep(decision, approved_model_ids={approved_model})
    stored_hash = repo.get_stored_context_hash(db, decision_id)
    dna = dna_engine.build_dna(decision, baseline.replayability.status, sweep=sweep, stored_context_hash=stored_hash)
    return dna.to_dict()


@app.get("/decisions/{decision_id}/risk", response_model=RiskAssessmentOut)
def get_risk(decision_id: str, db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    risk = assess_risk(decision)
    return RiskAssessmentOut(**risk.__dict__)


@app.get("/decisions/{decision_id}/governance", response_model=list[GovernanceFindingOut])
def get_governance(decision_id: str, approved_model: str = "fraud-v3.2", db: Session = Depends(get_db)):
    decision = repo.get_decision(db, decision_id)
    if not decision:
        raise HTTPException(404, f"Decision {decision_id} not found")
    findings = evaluate_controls(decision, approved_model_ids={approved_model})
    return [
        GovernanceFindingOut(control_id=f.control_id, control_name=f.control_name,
                              status=f.status.value, reason=f.reason, evidence=list(f.evidence))
        for f in findings
    ]


@app.get("/decisions/{decision_id}/events")
def get_events(decision_id: str, db: Session = Depends(get_db)):
    events = repo.list_events(db, decision_id)
    return [
        {"event_id": e.event_id, "timestamp": e.timestamp, "event_type": e.event_type, "payload": e.payload_json}
        for e in events
    ]


@app.post("/policies")
def create_policy(policy: PolicyIn, db: Session = Depends(get_db)):
    pv = PolicyVersion(policy_id=policy.policy_id, block_threshold=policy.block_threshold,
                        review_threshold=policy.review_threshold,
                        required_controls=tuple(policy.required_controls), description=policy.description)
    repo.upsert_policy(db, pv)
    return {"status": "ok", "policy_id": policy.policy_id}


@app.get("/policies")
def get_policies(db: Session = Depends(get_db)):
    return [
        {"policy_id": p.policy_id, "block_threshold": p.block_threshold, "review_threshold": p.review_threshold,
         "required_controls": p.required_controls_json, "description": p.description}
        for p in repo.list_policies(db)
    ]


@app.post("/models")
def create_model(model: ModelIn, db: Session = Depends(get_db)):
    mv = ModelVersion(model_id=model.model_id, weights=model.weights, base_rate=model.base_rate,
                       description=model.description)
    repo.upsert_model(db, mv)
    return {"status": "ok", "model_id": model.model_id}


@app.get("/models")
def get_models(db: Session = Depends(get_db)):
    return [
        {"model_id": m.model_id, "weights": m.weights_json, "base_rate": m.base_rate, "description": m.description}
        for m in repo.list_models(db)
    ]


@app.post("/incidents")
def create_incident(incident: IncidentIn, db: Session = Depends(get_db)):
    incident_id = f"INC-{uuid.uuid4().hex[:6]}"
    repo.create_incident(db, incident_id, incident.title, incident.description, incident.decision_ids,
                          affected_evidence_kind=incident.affected_evidence_kind)
    return {"incident_id": incident_id, "title": incident.title, "decision_ids": incident.decision_ids,
            "affected_evidence_kind": incident.affected_evidence_kind}


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str, db: Session = Depends(get_db)):
    record = repo.get_incident(db, incident_id)
    if not record:
        raise HTTPException(404, f"Incident {incident_id} not found")
    decisions = [repo.get_decision(db, did) for did in record.decision_ids_json]
    decisions = [d for d in decisions if d]
    return {
        "incident_id": record.incident_id, "title": record.title, "description": record.description,
        "created_at": record.created_at, "decision_count": len(decisions),
        "affected_evidence_kind": record.affected_evidence_kind,
        "model_versions": sorted({d.context.model_version.model_id for d in decisions}),
        "policy_versions": sorted({d.context.policy_version.policy_id for d in decisions}),
        "decisions": [_summary(d).model_dump() for d in decisions],
    }


@app.get("/incidents/{incident_id}/timeline")
def get_incident_timeline(incident_id: str, db: Session = Depends(get_db)):
    record = repo.get_incident(db, incident_id)
    if not record:
        raise HTTPException(404, f"Incident {incident_id} not found")
    timeline = []
    for did in record.decision_ids_json:
        events = repo.list_events(db, did)
        for e in events:
            timeline.append({"timestamp": e.timestamp, "decision_id": did, "event_type": e.event_type, "payload": e.payload_json})
    timeline.sort(key=lambda x: x["timestamp"])
    return timeline


@app.get("/incidents/{incident_id}/blast-radius")
def get_incident_blast_radius(incident_id: str, db: Session = Depends(get_db)):
    """Real, replay-derived blast radius: replayability breakdown across every decision in the
    incident, plus (if the incident names a suspected evidence kind) a per-decision counterfactual
    test of whether removing that evidence flips each decision's outcome."""
    record = repo.get_incident(db, incident_id)
    if not record:
        raise HTTPException(404, f"Incident {incident_id} not found")
    decisions = [repo.get_decision(db, did) for did in record.decision_ids_json]
    decisions = [d for d in decisions if d]
    report = incident_engine.analyze_blast_radius(incident_id, decisions, record.affected_evidence_kind)
    return report.to_dict()


@app.post("/policies/{policy_id}/impact-replay")
def policy_impact_replay(policy_id: str, new_policy: PolicyIn, db: Session = Depends(get_db)):
    """Replay all historical decisions under a new policy version and summarize impact."""
    decisions = repo.list_decisions(db, limit=1000)
    new_pv = PolicyVersion(policy_id=new_policy.policy_id, block_threshold=new_policy.block_threshold,
                            review_threshold=new_policy.review_threshold,
                            required_controls=tuple(new_policy.required_controls))
    changed, reviews, violations, unchanged = 0, 0, 0, 0
    changed_decisions = []
    for d in decisions:
        m = Mutation(mutation_id=f"POLICY-{uuid.uuid4().hex[:6]}", type=MutationType.CHANGE_POLICY,
                     target=d.context.policy_version.policy_id, before=d.context.policy_version.policy_id,
                     after=new_pv.policy_id, reason="policy impact replay",
                     payload={"policy_id": new_pv.policy_id, "block_threshold": new_pv.block_threshold,
                              "review_threshold": new_pv.review_threshold,
                              "required_controls": list(new_pv.required_controls)})
        result = run_counterfactual(d, [m])
        if result.diff.diverged:
            changed += 1
            changed_decisions.append({
                "decision_id": d.decision_id, "original_outcome": result.original_replay.outcome.value,
                "new_outcome": result.counterfactual_replay.outcome.value,
            })
            if result.counterfactual_replay.outcome.value == "REVIEW":
                reviews += 1
        else:
            unchanged += 1
    return {
        "old_policy": d.context.policy_version.policy_id if decisions else None,
        "new_policy": new_pv.policy_id,
        "historical_decisions": len(decisions),
        "changed_outcomes": changed,
        "required_human_review": reviews,
        "no_change": unchanged,
        "changed_decisions": changed_decisions,
    }
