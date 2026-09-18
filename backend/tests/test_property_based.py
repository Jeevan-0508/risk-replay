"""Property-based tests using Hypothesis, per the spec's testing requirements."""
from dataclasses import replace

from hypothesis import given, strategies as st

from app.golden_dataset import build_dec_001
from app.engines.decision_engine import decide
from app.engines.replay_engine import replay
from app.engines.mutation_engine import Mutation, apply_mutation
from app.domain.enums import MutationType


@given(st.integers(min_value=0, max_value=0))  # deterministic sanity repeat
def test_replay_of_unmutated_context_always_equals_original(_):
    d = build_dec_001()
    r = replay(d)
    assert r.outcome == d.decision


@given(st.floats(min_value=0.0, max_value=1.0))
def test_threshold_mutation_never_produces_score_outside_unit_interval(new_value):
    d = build_dec_001()
    m = Mutation(mutation_id="MT", type=MutationType.CHANGE_THRESHOLD, target="policy-17",
                 before="0.82", after=str(new_value), reason="property test",
                 payload={"field": "block_threshold", "value": new_value})
    mutated_ctx = apply_mutation(d.context, m)
    _, score, _ = decide(mutated_ctx)
    assert 0.0 <= score <= 1.0


@given(st.sampled_from(["E1", "E2", "E3", "E4"]))
def test_remove_then_readd_same_evidence_restores_score(evidence_id):
    d = build_dec_001()
    original_ev = next(e for e in d.context.evidence if e.evidence_id == evidence_id)
    remove = Mutation(mutation_id="R", type=MutationType.REMOVE_EVIDENCE, target=evidence_id,
                       before="present", after="absent", reason="pbt")
    removed_ctx = apply_mutation(d.context, remove)
    restore = Mutation(mutation_id="A", type=MutationType.ADD_EVIDENCE, target=evidence_id,
                        before="absent", after="present", reason="pbt",
                        payload={"evidence_id": evidence_id, "source": original_ev.source,
                                 "kind": original_ev.kind, "value": original_ev.value,
                                 "weight": original_ev.weight})
    restored_ctx = apply_mutation(removed_ctx, restore)
    _, restored_score, _ = decide(restored_ctx)
    _, original_score, _ = decide(d.context)
    assert abs(restored_score - original_score) < 1e-9
