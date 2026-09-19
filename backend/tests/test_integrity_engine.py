"""Tests for app.engines.integrity_engine -- Replay Integrity."""
import math
from dataclasses import replace

from app.golden_dataset import build_dec_001
from app.engines import integrity_engine


def test_valid_hashes_verified():
    d = build_dec_001()
    stored_hash = d.context.context_hash()
    report = integrity_engine.verify_integrity(d, stored_context_hash=stored_hash)
    assert report.status == "VERIFIED"
    assert report.findings == ()
    assert "context" in report.checked


def test_tampered_evidence_value_without_updating_hash_is_compromised():
    d = build_dec_001()
    ev = d.context.evidence[2]  # E3
    tampered_ev = replace(ev, value=0.01)  # value changed, content_hash left stale
    tampered_evidence = tuple(tampered_ev if e.evidence_id == "E3" else e for e in d.context.evidence)
    tampered_context = replace(d.context, evidence=tampered_evidence)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision)
    assert report.status == "COMPROMISED"
    types = {f.finding_type for f in report.findings}
    assert "EVIDENCE_HASH_MISMATCH" in types
    targets = {f.target for f in report.findings if f.finding_type == "EVIDENCE_HASH_MISMATCH"}
    assert "E3" in targets


def test_changed_input_payload_is_compromised():
    d = build_dec_001()
    tampered_input = replace(d.context.input_snapshot, payload={"transaction_id": "TXN-FORGED", "amount": 1.0, "currency": "USD"})
    tampered_context = replace(d.context, input_snapshot=tampered_input)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision)
    assert report.status == "COMPROMISED"
    assert any(f.finding_type == "INPUT_HASH_MISMATCH" for f in report.findings)


def test_changed_policy_after_recording_is_caught_via_context_hash():
    d = build_dec_001()
    stored_hash = d.context.context_hash()  # captured BEFORE tampering, as persistence would do
    tampered_policy = replace(d.context.policy_version, policy_id="policy-FORGED")
    tampered_context = replace(d.context, policy_version=tampered_policy)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision, stored_context_hash=stored_hash)
    assert report.status == "COMPROMISED"
    assert any(f.finding_type == "CONTEXT_HASH_MISMATCH" for f in report.findings)


def test_changed_model_after_recording_is_caught_via_context_hash():
    d = build_dec_001()
    stored_hash = d.context.context_hash()
    tampered_model = replace(d.context.model_version, model_id="fraud-FORGED")
    tampered_context = replace(d.context, model_version=tampered_model)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision, stored_context_hash=stored_hash)
    assert report.status == "COMPROMISED"
    assert any(f.finding_type == "CONTEXT_HASH_MISMATCH" for f in report.findings)


def test_missing_hash_is_unknown_not_compromised():
    d = build_dec_001()
    ev = d.context.evidence[0]
    unhashed_ev = replace(ev, content_hash="")
    unhashed_evidence = tuple(unhashed_ev if e.evidence_id == ev.evidence_id else e for e in d.context.evidence)
    tampered_context = replace(d.context, evidence=unhashed_evidence)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision)
    assert report.status == "UNKNOWN"
    assert any(f.finding_type == "MISSING_HASH" for f in report.findings)


def test_malformed_evidence_value_nan_detected():
    d = build_dec_001()
    ev = d.context.evidence[0]
    malformed_ev = replace(ev, value=math.nan)
    malformed_evidence = tuple(malformed_ev if e.evidence_id == ev.evidence_id else e for e in d.context.evidence)
    tampered_context = replace(d.context, evidence=malformed_evidence)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision)
    assert report.status == "UNKNOWN"
    assert any(f.finding_type == "MALFORMED_ARTIFACT" for f in report.findings)


def test_partial_integrity_reports_only_the_actually_tampered_target():
    d = build_dec_001()
    stored_hash = d.context.context_hash()
    ev = d.context.evidence[1]  # E2 tampered, E1/E3/E4 left alone
    tampered_ev = replace(ev, value=0.999)
    tampered_evidence = tuple(tampered_ev if e.evidence_id == "E2" else e for e in d.context.evidence)
    tampered_context = replace(d.context, evidence=tampered_evidence)
    tampered_decision = replace(d, context=tampered_context)

    report = integrity_engine.verify_integrity(tampered_decision, stored_context_hash=stored_hash)
    assert report.status == "COMPROMISED"
    mismatch_targets = {f.target for f in report.findings if f.finding_type == "EVIDENCE_HASH_MISMATCH"}
    assert mismatch_targets == {"E2"}
    # context-level mismatch also fires (E2's evidence hash feeds context_hash) but
    # E1/E3/E4 must not be individually flagged.
    assert not any(f.target in ("E1", "E3", "E4") for f in report.findings)


def test_no_stored_context_hash_skips_context_level_check_without_error():
    d = build_dec_001()
    report = integrity_engine.verify_integrity(d, stored_context_hash=None)
    assert "context" not in report.checked
    assert report.status == "VERIFIED"


def test_not_checked_artifacts_are_explicitly_disclosed():
    d = build_dec_001()
    report = integrity_engine.verify_integrity(d)
    assert len(report.not_checked) >= 2
    assert any("model_version" in n for n in report.not_checked)
    assert any("tool_invocations" in n for n in report.not_checked)


def test_deterministic_report():
    d = build_dec_001()
    stored_hash = d.context.context_hash()
    a = integrity_engine.verify_integrity(d, stored_context_hash=stored_hash)
    b = integrity_engine.verify_integrity(d, stored_context_hash=stored_hash)
    assert a.to_dict() == b.to_dict()


def test_to_dict_shape():
    d = build_dec_001()
    report = integrity_engine.verify_integrity(d, stored_context_hash=d.context.context_hash())
    keys = set(report.to_dict().keys())
    assert keys == {"status", "findings", "checked", "not_checked"}
