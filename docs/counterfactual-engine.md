# Counterfactual Engine

## Mechanics

1. `mutation_engine.apply_mutation(context, mutation)` returns a **new** `DecisionContext`.
   The original is a frozen dataclass; nothing mutates in place.
2. `counterfactual_engine.run_counterfactual(decision, mutations)`:
   - replays the decision's own original context (baseline)
   - folds all mutations onto a copy of the context (`apply_mutations`)
   - replays the mutated context
   - diffs the two replay results
3. Single vs multi-variable: `is_multi_variable = len(mutations) > 1`. This flag changes
   how the causal engine is allowed to word its finding -- a multi-variable
   counterfactual can never be reported as `DECISION_CRITICAL` for one variable,
   because isolating one variable's effect requires its own single-variable run.

## Supported mutation types

`REMOVE_EVIDENCE`, `ADD_EVIDENCE`, `MODIFY_EVIDENCE`, `CHANGE_POLICY`, `CHANGE_MODEL`,
`CHANGE_THRESHOLD`, `REMOVE_TOOL_RESULT`, `MODIFY_TOOL_RESULT`, `CHANGE_INPUT`,
`DISABLE_CONTROL`. Each is a small, targeted transform in
`app/engines/mutation_engine.py`; unsupported combinations raise `MutationError` rather
than silently no-opping.

## Reversibility

`tests/test_mutation_and_counterfactual.py::test_restoring_evidence_restores_original_decision`
and the Hypothesis property `test_remove_then_readd_same_evidence_restores_score` both
assert: remove evidence, then add it back with identical fields, and the decision score
is bit-for-bit (within float tolerance) what it was before. This is what "the engine is
not lying to you" looks like as a test.

## Forensic Sweep

`sweep_engine.run_forensic_sweep()` calls `run_counterfactual()` once per auto-generated single-variable mutation -- it does not reimplement this pipeline. See `docs/forensic-sweep.md` for the full design, including why only `REMOVE_EVIDENCE`/`REMOVE_TOOL_RESULT`/`DISABLE_CONTROL` are auto-generated.
