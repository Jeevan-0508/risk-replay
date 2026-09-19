"""backend/app/seed.py -- load the golden synthetic dataset into the database.
Run: python -m app.seed
"""
from app.db.database import SessionLocal, init_db
from app.db import repository as repo
from app.golden_dataset import build_all_decisions, build_fraud_v32, build_policy_17, build_policy_18


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        repo.upsert_model(db, build_fraud_v32())
        repo.upsert_policy(db, build_policy_17())
        repo.upsert_policy(db, build_policy_18())
        decisions = build_all_decisions()
        for d in decisions:
            repo.save_decision(db, d)
        incident_decisions = decisions[:15]
        repo.create_incident(
            db, "INC-0042", "Elevated fraud-block rate on account cluster 4471",
            "Synthetic demo incident grouping decisions for the killer-demo replay. Investigation "
            "suspects the shared identity-risk signal, so the incident is tagged with that evidence "
            "kind for a real per-decision blast-radius counterfactual test.",
            [d.decision_id for d in incident_decisions],
            affected_evidence_kind="identity_risk",
        )
        print(f"Seeded {len(decisions)} decisions, 1 model, 2 policies, 1 incident "
              f"({len(incident_decisions)} decisions in incident).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
