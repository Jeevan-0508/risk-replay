"""Tests for app.engines.incident_engine -- Incident Blast-Radius Forensics."""
from app.engines import incident_engine
from app.golden_dataset import build_all_decisions


def _incident_decisions():
    return build_all_decisions()[:15]


def test_replayability_breakdown_sums_to_total():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind=None)
    assert report.affected_decisions == len(decisions)
    assert (report.replayable_count + report.partially_replayable_count
            + report.non_replayable_count) == len(decisions)


def test_no_evidence_kind_is_an_honest_no_op():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind=None)
    assert report.decisions_with_dependency == 0
    assert report.decisions_changed == 0
    assert report.decisions_unchanged == 0
    assert report.common_replay_dependency is None
    for impact in report.decision_impacts:
        assert impact.has_dependency is False
        assert impact.evidence_id is None
        assert impact.baseline_outcome is None
        assert impact.counterfactual_outcome is None
        assert impact.changed is False


def test_identity_risk_kind_finds_dependency_on_every_decision():
    # every synthetic decision has exactly one evidence item of each of the
    # 4 model weight kinds, including identity_risk -- see golden_dataset.build_all_decisions
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    assert report.decisions_with_dependency == len(decisions)
    for impact in report.decision_impacts:
        assert impact.has_dependency is True
        assert impact.evidence_id is not None
        assert impact.baseline_outcome is not None
        assert impact.counterfactual_outcome is not None


def test_unknown_evidence_kind_finds_no_dependency():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="nonexistent_kind")
    assert report.decisions_with_dependency == 0
    assert report.decisions_changed == 0
    assert report.common_replay_dependency is None


def test_decisions_changed_never_exceeds_decisions_with_dependency():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    assert report.decisions_changed <= report.decisions_with_dependency
    assert report.decisions_unchanged == report.decisions_with_dependency - report.decisions_changed


def test_common_replay_dependency_shape_and_wording():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    dep = report.common_replay_dependency
    assert dep is not None
    assert dep["evidence_kind"] == "identity_risk"
    assert dep["decisions_changed"] == report.decisions_changed
    assert "->" in dep["label"]
    assert str(report.decisions_changed) in dep["label"]
    assert "not asserted as the real-world root cause" in dep["note"]
    assert "root cause" not in dep["label"]


def test_affected_policy_model_source_control_sets_are_real():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind=None)
    expected_models = sorted({d.context.model_version.model_id for d in decisions})
    expected_policies = sorted({d.context.policy_version.policy_id for d in decisions})
    assert list(report.affected_models) == expected_models
    assert list(report.affected_policies) == expected_policies
    assert len(report.affected_evidence_sources) > 0


def test_determinism_same_input_same_output():
    decisions = _incident_decisions()
    r1 = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    r2 = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    d1 = r1.to_dict(); d2 = r2.to_dict()
    d1.pop("timestamp"); d2.pop("timestamp")
    assert d1 == d2


def test_to_dict_shape():
    decisions = _incident_decisions()
    report = incident_engine.analyze_blast_radius("INC-TEST", decisions, affected_evidence_kind="identity_risk")
    d = report.to_dict()
    for key in ("incident_id", "affected_evidence_kind", "affected_decisions", "replayable_count",
                "partially_replayable_count", "non_replayable_count", "decisions_with_dependency",
                "decisions_changed", "decisions_unchanged", "affected_policies", "affected_models",
                "affected_evidence_sources", "affected_controls", "common_replay_dependency",
                "decision_impacts", "timestamp"):
        assert key in d
    assert isinstance(d["decision_impacts"], list)
    assert isinstance(d["decision_impacts"][0], dict)


def test_empty_decision_list_is_safe():
    report = incident_engine.analyze_blast_radius("INC-EMPTY", [], affected_evidence_kind="identity_risk")
    assert report.affected_decisions == 0
    assert report.decisions_with_dependency == 0
    assert report.common_replay_dependency is None
