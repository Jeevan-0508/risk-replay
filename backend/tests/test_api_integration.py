"""Integration tests for the FastAPI app using an isolated in-memory SQLite DB."""
import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.db.database as dbmod
from app.db.database import Base, get_db
from app.db import repository as repo
from app.golden_dataset import build_dec_001, build_all_decisions, build_fraud_v32, build_policy_17, build_policy_18


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    from app.api.main import app as fastapi_app

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db

    db = TestingSessionLocal()
    repo.upsert_model(db, build_fraud_v32())
    repo.upsert_policy(db, build_policy_17())
    repo.upsert_policy(db, build_policy_18())
    decisions = build_all_decisions()
    for d in decisions:
        repo.save_decision(db, d)
    repo.create_incident(db, "INC-TEST", "Test incident", "", [decisions[0].decision_id])
    db.close()

    with TestClient(fastapi_app) as c:
        yield c

    fastapi_app.dependency_overrides.clear()


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_list_and_get_decision(client):
    r = client.get("/decisions")
    assert r.status_code == 200
    assert len(r.json()) == 40

    r = client.get("/decisions/DEC-001")
    assert r.status_code == 200
    body = r.json()
    assert body["decision"] == "BLOCK"
    assert body["replayability_status"] == "REPLAYABLE"


def test_get_decision_404(client):
    r = client.get("/decisions/NOPE")
    assert r.status_code == 404


def test_replay_endpoint_matches_original(client):
    r = client.post("/decisions/DEC-001/replay")
    assert r.status_code == 200
    assert r.json()["outcome"] == "BLOCK"


def test_counterfactual_killer_demo_via_api(client):
    r = client.post("/decisions/DEC-001/counterfactual", json={
        "mutations": [{"type": "REMOVE_EVIDENCE", "target": "E3", "reason": "api test"}]
    })
    assert r.status_code == 200
    body = r.json()
    assert body["original_outcome"] == "BLOCK"
    assert body["counterfactual_outcome"] == "ALLOW"
    assert body["diverged"] is True
    assert body["causal_status"] == "DECISION_CRITICAL"


def test_counterfactual_invalid_target_returns_400(client):
    r = client.post("/decisions/DEC-001/counterfactual", json={
        "mutations": [{"type": "REMOVE_EVIDENCE", "target": "E999", "reason": "bad target"}]
    })
    assert r.status_code == 400


def test_lineage_endpoint(client):
    r = client.get("/decisions/DEC-001/lineage")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) > 0
    assert len(body["edges"]) > 0


def test_risk_and_governance_endpoints(client):
    r = client.get("/decisions/DEC-001/risk")
    assert r.status_code == 200
    assert r.json()["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    r = client.get("/decisions/DEC-001/governance")
    assert r.status_code == 200
    findings = r.json()
    assert any(f["control_id"] == "C-17" for f in findings)


def test_incident_endpoints(client):
    r = client.get("/incidents/INC-TEST")
    assert r.status_code == 200
    assert r.json()["decision_count"] == 1

    r = client.get("/incidents/INC-TEST/timeline")
    assert r.status_code == 200

    r = client.get("/incidents/INC-TEST/blast-radius")
    assert r.status_code == 200


def test_policy_impact_replay(client):
    r = client.post("/policies/policy-18/impact-replay", json={
        "policy_id": "policy-18", "block_threshold": 0.75, "review_threshold": 0.45,
        "required_controls": ["C-17", "C-08"],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["historical_decisions"] == 40
    assert body["changed_outcomes"] >= 0
    assert body["changed_outcomes"] + body["no_change"] == 40


def test_create_and_list_policy(client):
    r = client.post("/policies", json={
        "policy_id": "policy-99", "block_threshold": 0.9, "review_threshold": 0.6, "required_controls": [],
    })
    assert r.status_code == 200
    r = client.get("/policies")
    ids = [p["policy_id"] for p in r.json()]
    assert "policy-99" in ids


def test_forensic_sweep_endpoint_flips_e3_to_allow(client):
    r = client.post("/decisions/DEC-001/forensic-sweep", json={"approved_model": "fraud-v3.2"})
    assert r.status_code == 200
    body = r.json()
    assert body["baseline_outcome"] == "BLOCK"
    e3 = next(e for e in body["experiments"] if e["variable"] == "E3")
    assert e3["counterfactual_outcome"] == "ALLOW"
    assert e3["diverged"] is True
    assert e3["causal_status"] == "DECISION_CRITICAL"
    assert body["summary"]["most_sensitive_variable"] == "E3"
    assert any(u["mutation_type"] == "CHANGE_THRESHOLD" for u in body["unsupported_mutation_types"])


def test_forensic_sweep_persists_and_can_be_retrieved(client):
    r = client.post("/decisions/DEC-001/forensic-sweep", json={"approved_model": "fraud-v3.2"})
    sweep_id = r.json()["sweep_id"]

    r2 = client.get(f"/decisions/DEC-001/forensic-sweeps/{sweep_id}")
    assert r2.status_code == 200
    assert r2.json()["sweep_id"] == sweep_id

    r3 = client.get("/decisions/DEC-001/forensic-sweeps")
    assert r3.status_code == 200
    assert any(s["sweep_id"] == sweep_id for s in r3.json())


def test_forensic_sweep_404_for_unknown_decision(client):
    r = client.post("/decisions/NOPE/forensic-sweep", json={})
    assert r.status_code == 404


def test_forensic_sweep_governance_impact_present_in_response(client):
    r = client.post("/decisions/DEC-001/forensic-sweep", json={"approved_model": "fraud-v3.2"})
    body = r.json()
    e3 = next(e for e in body["experiments"] if e["variable"] == "E3")
    control_ids = {g["control_id"] for g in e3["governance_impact"]}
    assert control_ids == {"C-17", "C-08"}
