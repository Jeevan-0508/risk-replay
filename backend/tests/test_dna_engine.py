"""Tests for app.engines.dna_engine -- Decision DNA."""
from app.golden_dataset import build_dec_001
from app.engines import dna_engine
from app.engines.replay_engine import replay
from app.engines.sweep_engine import run_forensic_sweep


def test_dna_without_sweep_reports_none_for_critical_fields():
    d = build_dec_001()
    baseline = replay(d)
    dna = dna_engine.build_dna(d, baseline.replayability.status)
    assert dna.decision_id == "DEC-001"
    assert dna.model == "fraud-v3.2"
    assert dna.policy == "policy-17"
    assert dna.baseline_score == 0.834
    assert dna.outcome == "BLOCK"
    assert dna.zone == "BLOCK"
    assert dna.evidence_count == 4
    assert dna.replayability == "REPLAYABLE"
    assert dna.integrity_status == "VERIFIED"
    # No sweep supplied -> explicit None, not a fabricated empty list.
    assert dna.decision_critical_variables is None
    assert dna.governance_affected_controls is None


def test_dna_with_sweep_reports_real_critical_variables():
    d = build_dec_001()
    baseline = replay(d)
    sweep = run_forensic_sweep(d)
    dna = dna_engine.build_dna(d, baseline.replayability.status, sweep=sweep)
    assert dna.decision_critical_variables is not None
    assert set(dna.decision_critical_variables) == {"E1", "E2", "E3", "E4"}
    assert "C-17" in dna.governance_affected_controls


def test_dna_boundary_margin_matches_boundary_engine():
    d = build_dec_001()
    baseline = replay(d)
    dna = dna_engine.build_dna(d, baseline.replayability.status)
    policy = d.context.policy_version
    expected_margin = round(policy.block_threshold - d.risk_score, 4)
    assert dna.boundary_margin == expected_margin


def test_dna_is_deterministic():
    d = build_dec_001()
    baseline = replay(d)
    sweep = run_forensic_sweep(d)
    a = dna_engine.build_dna(d, baseline.replayability.status, sweep=sweep)
    b = dna_engine.build_dna(d, baseline.replayability.status, sweep=sweep)
    assert a.to_dict() == b.to_dict()


def test_dna_to_dict_has_all_spec_keys():
    d = build_dec_001()
    baseline = replay(d)
    dna = dna_engine.build_dna(d, baseline.replayability.status)
    keys = set(dna.to_dict().keys())
    assert keys == {
        "decision_id", "model", "policy", "baseline_score", "outcome",
        "boundary_margin", "zone", "replayability", "evidence_count",
        "decision_critical_variables", "governance_affected_controls",
        "integrity_status",
    }
