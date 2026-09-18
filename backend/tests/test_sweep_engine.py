"""
backend/tests/test_sweep_engine.py

Tests for the Forensic Sweep engine: determinism, baseline integrity,
mutation isolation, replay identity, boundary cases, evidence-removal edge
cases, non-causality guard on multi-mutation, failure paths, and score
bounds. See docs/forensic-sweep.md for the design rationale.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from hypothesis import given, strategies as st

from app.domain.enums import CausalStatus, ReplayabilityStatus
from app.domain.models import ControlDefinition, Evidence, EvidenceClassification, ToolInvocation
from app.engines.replay_engine import replay
from app.engines.sweep_engine import generate_mutations, run_forensic_sweep
from app.golden_dataset import build_dec_001


def test_generate_mutations_is_pure_and_deterministic():
    ctx = build_dec_001().context
    m1 = generate_mutations(ctx, "DEC-001")
    m2 = generate_mutations(ctx, "DEC-001")
    assert [(m.mutation_id, m.type, m.target) for m in m1] == [(m.mutation_id, m.type, m.target) for m in m2]


def test_generate_mutations_covers_evidence_tools_controls_in_order():
    ctx = build_dec_001().context
    muts = generate_mutations(ctx, "DEC-001")
    assert len(muts) == len(ctx.evidence) + len(ctx.tool_invocations) + len(ctx.control_definitions)
    evidence_targets = [m.target for m in muts if m.type.value == "REMOVE_EVIDENCE"]
    assert evidence_targets == [e.evidence_id for e in ctx.evidence]


def test_sweep_is_deterministic_across_runs():
    decision = build_dec_001()
    r1 = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    r2 = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    assert [e.experiment_id for e in r1.experiments] == [e.experiment_id for e in r2.experiments]
    assert [e.counterfactual_score for e in r1.experiments] == [e.counterfactual_score for e in r2.experiments]
    assert [e.causal_status for e in r1.experiments] == [e.causal_status for e in r2.experiments]


def test_sweep_never_mutates_original_decision():
    decision = build_dec_001()
    before_evidence = decision.context.evidence
    before_score = decision.risk_score
    run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    assert decision.context.evidence == before_evidence
    assert decision.risk_score == before_score


def test_replay_of_original_context_equals_baseline_before_and_after_sweep():
    decision = build_dec_001()
    r_before = replay(decision)
    run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    r_after = replay(decision)
    assert r_before.outcome == r_after.outcome == decision.decision
    assert r_before.score == r_after.score == decision.risk_score


def test_mutation_isolation_no_leakage_between_experiments():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    # every experiment's baseline score must equal the decision's own risk_score --
    # if a prior mutation had leaked in, some baseline_score would drift.
    for exp in result.experiments:
        assert exp.baseline_score == round(decision.risk_score, 4)


def test_removing_e3_flips_block_to_allow_and_is_decision_critical():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    e3 = next(e for e in result.experiments if e.variable == "E3")
    assert e3.baseline_outcome == "BLOCK"
    assert e3.counterfactual_outcome == "ALLOW"
    assert e3.diverged is True
    assert e3.causal_status == CausalStatus.DECISION_CRITICAL.value
    assert e3.score_delta == pytest.approx(-0.285, abs=1e-6)


def test_removing_e2_is_not_decision_critical_when_it_does_not_flip_outcome():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    e2 = next(e for e in result.experiments if e.variable == "E2")
    if not e2.diverged:
        assert e2.causal_status == CausalStatus.DECISION_IRRELEVANT.value


def test_summary_counts_are_computed_not_hardcoded():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    s = result.summary
    assert s.experiment_count == len(result.experiments)
    critical = sum(1 for e in result.experiments if e.causal_status == "DECISION_CRITICAL")
    irrelevant = sum(1 for e in result.experiments if e.causal_status == "DECISION_IRRELEVANT")
    contributory = sum(1 for e in result.experiments if e.causal_status == "CONTRIBUTORY")
    assert s.decision_critical_count == critical
    assert s.decision_irrelevant_count == irrelevant
    assert s.contributory_count == contributory
    diverged = sum(1 for e in result.experiments if e.diverged)
    assert s.divergence_ratio == round(diverged / len(result.experiments), 4)
    assert s.most_sensitive_variable == "E3"  # E3 has the largest |score_delta|


def test_unsupported_mutation_types_are_reported_not_silently_dropped():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    types = {u["mutation_type"] for u in result.unsupported_mutation_types}
    assert "CHANGE_THRESHOLD" in types
    assert "CHANGE_POLICY" in types
    assert "CHANGE_MODEL" in types
    for u in result.unsupported_mutation_types:
        assert u["reason"]  # never an empty/fabricated reason


def test_score_bounds_hold_for_every_experiment():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    for e in result.experiments:
        assert 0.0 <= e.baseline_score <= 1.0
        assert 0.0 <= e.counterfactual_score <= 1.0
        assert 0.0 <= e.sensitivity <= 1.0


def test_boundary_crossed_flag_matches_outcome_flip_direction():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    e3 = next(e for e in result.experiments if e.variable == "E3")
    assert e3.boundary["crossed_block_threshold"] is True
    assert e3.boundary["direction"] == "decrease"


def test_governance_impact_reuses_governance_engine_and_is_control_scoped():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    e3 = next(e for e in result.experiments if e.variable == "E3")
    control_ids = {g["control_id"] for g in e3.governance_impact}
    assert control_ids == {"C-17", "C-08"}


def test_multi_mutation_never_produced_by_auto_sweep_stays_single_variable():
    decision = build_dec_001()
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    for e in result.experiments:
        assert e.mutation_type in ("REMOVE_EVIDENCE", "REMOVE_TOOL_RESULT", "DISABLE_CONTROL")
        assert " and " not in e.mutation_summary


def test_missing_evidence_edge_case_last_item_removed_still_replayable():
    """Removing the last remaining piece of evidence of a given kind must not
    crash -- score just drops that contribution to zero."""
    decision = build_dec_001()
    # Build a context with only one evidence item to exercise the "last evidence" edge.
    only_one = replace(decision.context, evidence=(decision.context.evidence[0],))
    minimal_decision = replace(decision, context=only_one)
    result = run_forensic_sweep(minimal_decision, approved_model_ids={"fraud-v3.2"})
    assert len(result.experiments) == 1 + len(only_one.tool_invocations) + len(only_one.control_definitions)
    ev_exp = next(e for e in result.experiments if e.variable_kind == "evidence")
    assert ev_exp.counterfactual_score >= 0.0


def test_no_evidence_no_tools_no_controls_yields_empty_sweep_not_a_crash():
    decision = build_dec_001()
    empty_ctx = replace(decision.context, evidence=(), tool_invocations=(), control_definitions=())
    empty_decision = replace(decision, context=empty_ctx)
    result = run_forensic_sweep(empty_decision, approved_model_ids={"fraud-v3.2"})
    assert result.experiments == ()
    assert result.summary.experiment_count == 0
    assert result.summary.most_sensitive_variable is None


def test_non_deterministic_tool_removal_still_yields_explicit_replayability_status():
    decision = build_dec_001()
    nd_tool = ToolInvocation(tool_id="T-ND", tool_name="flaky-service", deterministic=False)
    ctx = replace(decision.context, tool_invocations=decision.context.tool_invocations + (nd_tool,))
    d2 = replace(decision, context=ctx)
    result = run_forensic_sweep(d2, approved_model_ids={"fraud-v3.2"})
    for e in result.experiments:
        assert e.replayability_status in (
            ReplayabilityStatus.REPLAYABLE.value,
            ReplayabilityStatus.PARTIALLY_REPLAYABLE.value,
            ReplayabilityStatus.NON_REPLAYABLE.value,
        )


def test_missing_model_id_yields_non_replayable_not_a_fabricated_result():
    decision = build_dec_001()
    broken_model = replace(decision.context.model_version, model_id="")
    ctx = replace(decision.context, model_version=broken_model)
    d2 = replace(decision, context=ctx)
    result = run_forensic_sweep(d2, approved_model_ids={"fraud-v3.2"})
    assert len(result.experiments) > 0
    for e in result.experiments:
        assert e.replayability_status == ReplayabilityStatus.NON_REPLAYABLE.value


def test_duplicate_evidence_ids_do_not_crash_generation_or_sweep():
    decision = build_dec_001()
    dup = Evidence(evidence_id="E1", source="risk-engine", kind="velocity_signal", value=0.9, weight=0.25,
                    classification=EvidenceClassification.INTERNAL).with_hash()
    ctx = replace(decision.context, evidence=decision.context.evidence + (dup,))
    d2 = replace(decision, context=ctx)
    result = run_forensic_sweep(d2, approved_model_ids={"fraud-v3.2"})
    # generate_mutations produces one mutation per E1 occurrence; mutation_engine
    # removes ALL evidence items matching that target id (documented behaviour of
    # apply_mutation), so this must not raise -- it must just run.
    assert len(result.experiments) >= len(ctx.evidence)


def test_adversarial_tampered_value_out_of_range_does_not_crash_scoring():
    decision = build_dec_001()
    tampered = replace(decision.context.evidence[0], value=999.0)
    ctx = replace(decision.context, evidence=(tampered,) + decision.context.evidence[1:])
    d2 = replace(decision, context=ctx)
    result = run_forensic_sweep(d2, approved_model_ids={"fraud-v3.2"})
    for e in result.experiments:
        assert 0.0 <= e.counterfactual_score <= 1.0


def test_adversarial_negative_threshold_does_not_crash_boundary_analysis():
    decision = build_dec_001()
    bad_policy = replace(decision.context.policy_version, block_threshold=-0.5)
    ctx = replace(decision.context, policy_version=bad_policy)
    d2 = replace(decision, context=ctx)
    result = run_forensic_sweep(d2, approved_model_ids={"fraud-v3.2"})
    for e in result.experiments:
        assert 0.0 <= e.sensitivity <= 1.0


@given(
    remove_idx=st.integers(min_value=0, max_value=3),
)
def test_property_removing_any_single_evidence_item_matches_manual_counterfactual(remove_idx):
    from app.engines.counterfactual_engine import run_counterfactual
    decision = build_dec_001()
    ev = decision.context.evidence[remove_idx]
    result = run_forensic_sweep(decision, approved_model_ids={"fraud-v3.2"})
    exp = next(e for e in result.experiments if e.variable == ev.evidence_id and e.variable_kind == "evidence")
    from app.engines.mutation_engine import Mutation, MutationType as MT
    manual = Mutation(mutation_id="MANUAL", type=MT.REMOVE_EVIDENCE, target=ev.evidence_id,
                       before="", after="", reason="parity check")
    manual_cf = run_counterfactual(decision, [manual], counterfactual_id="MANUAL-CF")
    assert exp.counterfactual_score == round(manual_cf.counterfactual_replay.score, 4)
    assert exp.counterfactual_outcome == manual_cf.counterfactual_replay.outcome.value
