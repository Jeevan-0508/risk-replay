import pytest
from app.golden_dataset import build_dec_001
from app.engines.mutation_engine import Mutation, apply_mutation, MutationError
from app.domain.enums import MutationType
from app.engines.counterfactual_engine import run_counterfactual
from app.engines.causal_engine import analyze


def test_remove_evidence_e3_flips_block_to_allow():
    d = build_dec_001()
    m = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3",
                 before="present", after="absent", reason="demo")
    cf = run_counterfactual(d, [m])
    assert cf.original_replay.outcome.value == "BLOCK"
    assert cf.counterfactual_replay.outcome.value == "ALLOW"
    assert cf.diff.diverged is True


def test_causal_finding_is_decision_critical_for_single_variable_flip():
    d = build_dec_001()
    m = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3",
                 before="present", after="absent", reason="demo")
    cf = run_counterfactual(d, [m])
    finding = analyze(cf)
    assert finding.status.value == "DECISION_CRITICAL"


def test_tiny_evidence_perturbation_does_not_change_decision():
    """A small perturbation to one evidence value that doesn't cross either
    threshold boundary should not flip the outcome -- classified DECISION_IRRELEVANT."""
    d = build_dec_001()
    m = Mutation(mutation_id="M2", type=MutationType.MODIFY_EVIDENCE, target="E1",
                 before="0.9", after="0.89", reason="demo",
                 payload={"value": 0.89})
    cf = run_counterfactual(d, [m])
    assert cf.diff.diverged is False
    finding = analyze(cf)
    assert finding.status.value == "DECISION_IRRELEVANT"


def test_restoring_evidence_restores_original_decision():
    """Reversing a mutation should restore the original outcome (round-trip)."""
    d = build_dec_001()
    remove = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3",
                       before="present", after="absent", reason="demo")
    mutated_ctx = apply_mutation(d.context, remove)

    original_e3 = next(e for e in d.context.evidence if e.evidence_id == "E3")
    restore = Mutation(mutation_id="M1R", type=MutationType.ADD_EVIDENCE, target="E3",
                        before="absent", after="present", reason="revert",
                        payload={"evidence_id": "E3", "source": original_e3.source,
                                 "kind": original_e3.kind, "value": original_e3.value,
                                 "weight": original_e3.weight})
    restored_ctx = apply_mutation(mutated_ctx, restore)

    from app.engines.decision_engine import decide
    outcome, score, _ = decide(restored_ctx)
    assert outcome == d.decision
    assert abs(score - d.risk_score) < 1e-9


def test_mutation_on_nonexistent_target_raises():
    d = build_dec_001()
    m = Mutation(mutation_id="MX", type=MutationType.REMOVE_EVIDENCE, target="E999",
                 before="present", after="absent", reason="demo")
    with pytest.raises(MutationError):
        apply_mutation(d.context, m)


def test_multi_variable_counterfactual_is_flagged_contributory_not_critical():
    d = build_dec_001()
    m1 = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3",
                  before="present", after="absent", reason="demo")
    m2 = Mutation(mutation_id="M2", type=MutationType.CHANGE_THRESHOLD, target="policy-17",
                  before="0.82", after="0.5", reason="demo",
                  payload={"field": "block_threshold", "value": 0.5})
    cf = run_counterfactual(d, [m1, m2])
    assert cf.is_multi_variable is True
    finding = analyze(cf)
    assert finding.status.value in ("CONTRIBUTORY", "DECISION_IRRELEVANT")
