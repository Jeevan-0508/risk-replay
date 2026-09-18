from app.golden_dataset import build_dec_001
from app.engines.mutation_engine import Mutation
from app.domain.enums import MutationType
from app.engines.counterfactual_engine import run_counterfactual
from app.engines.diff_engine import diff_decision
from app.engines.risk_engine import assess_risk
from app.engines.governance_engine import evaluate_controls
from app.engines.replay_engine import replay


def test_diff_reports_field_level_changes():
    d = build_dec_001()
    m = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3",
                 before="present", after="absent", reason="demo")
    cf = run_counterfactual(d, [m])
    diff = cf.diff
    decision_field = next(f for f in diff.fields if f.field == "decision")
    assert decision_field.changed is True
    assert decision_field.original == "BLOCK"
    assert decision_field.replay == "ALLOW"


def test_risk_assessment_has_documented_formulas():
    d = build_dec_001()
    risk = assess_risk(d)
    assert risk.risk_level.value in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert set(risk.formulas.keys()) >= {
        "decision_risk", "evidence_completeness", "control_coverage",
    }
    assert risk.evidence_completeness == 1.0  # all golden evidence has content_hash


def test_governance_flags_missing_human_review():
    d = build_dec_001()
    findings = evaluate_controls(d, approved_model_ids={"fraud-v3.2"})
    human_oversight = next(f for f in findings if f.control_id == "C-17")
    assert human_oversight.status.value == "FAILED"


def test_governance_satisfied_for_approved_model():
    d = build_dec_001()
    findings = evaluate_controls(d, approved_model_ids={"fraud-v3.2"})
    model_control = next(f for f in findings if f.control_id == "C-08")
    assert model_control.status.value == "SATISFIED"


def test_governance_fails_for_unapproved_model():
    d = build_dec_001()
    findings = evaluate_controls(d, approved_model_ids={"some-other-model"})
    model_control = next(f for f in findings if f.control_id == "C-08")
    assert model_control.status.value == "FAILED"
