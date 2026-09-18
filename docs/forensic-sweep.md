# Forensic Sweep

## What it is

One click, one deterministic scan: for a single decision, automatically build and run
one single-variable counterfactual experiment per evidence item, tool result and control
already present in that decision's recorded context, then rank the results by
sensitivity. It is not a new causal method -- it is `counterfactual_engine.run_counterfactual`
called once per auto-generated `Mutation`, orchestrated by `app/engines/sweep_engine.py`.

## Why only three mutation types are auto-generated

`generate_mutations(context, decision_id)` only emits `REMOVE_EVIDENCE`,
`REMOVE_TOOL_RESULT` and `DISABLE_CONTROL` -- one per item that already exists in the
context. These are the only mutation types where "what to test" has an unambiguous,
non-fabricated answer: remove the thing that's there.

`CHANGE_POLICY`, `CHANGE_MODEL`, `CHANGE_THRESHOLD`, `ADD_EVIDENCE`, `MODIFY_EVIDENCE`,
`MODIFY_TOOL_RESULT` and `CHANGE_INPUT` are **not** auto-generated, because doing so
would require inventing a hypothetical replacement value (a new threshold, a new model,
a new evidence value) with no basis in the historical record. Picking that value
automatically would mean the sweep is silently choosing what to test, and that choice
would look like a finding. Instead, the sweep reports these types in
`unsupported_mutation_types` with the specific reason, every run -- nothing is silently
dropped. They remain fully available as **manual** counterfactuals through the existing
Replay Lab / `POST /decisions/{id}/counterfactual`, where a human investigator picks the
hypothetical value and owns that choice.

## Pipeline

```
decision.context (frozen baseline)
  -> generate_mutations()            pure, deterministic, same order every time
  -> for each mutation, independently:
       run_counterfactual(decision, [mutation])   fresh baseline each time, no leakage
       causal_engine.analyze()                    DECISION_CRITICAL / IRRELEVANT / CONTRIBUTORY / NON_REPLAYABLE
       diff_engine.decision_sensitivity()          same formula as risk_engine, reused not reinvented
       boundary analysis                           margin to nearest threshold, crossed?, direction
       governance_engine.evaluate_controls()       run against baseline context and mutated context, diffed
  -> ForensicSweepResult (experiments + computed summary + unsupported list)
```

Every experiment starts from `decision.context` untouched -- `run_forensic_sweep` never
folds one experiment's mutation into the next. `test_mutation_isolation_no_leakage_between_experiments`
and `test_sweep_never_mutates_original_decision` in
`backend/tests/test_sweep_engine.py` assert this directly.

## Sensitivity formula (reused, not invented)

```
decision_sensitivity(original_score, mutated_score, block_threshold)
  = min(1, |mutated_score - original_score| / block_threshold)
```

This is `diff_engine.decision_sensitivity`, the same formula `risk_engine.assess_risk`
already used for a single counterfactual. The sweep calls it once per experiment; there
is exactly one implementation of this formula in the whole codebase.

## Deterministic IDs

`sweep_id = SWEEP-{decision_id}`, `experiment_id = {sweep_id}-{NNN}` in generation order
(evidence, then tools, then controls -- the same order every run for the same context).
Persistence uses a separate `uuid`-free primary key (`sweep_id` itself), consistent with
how `MutationRecord`/`CounterfactualRecord` key off caller-supplied ids.

## API

- `POST /decisions/{id}/forensic-sweep` (body: `{"approved_model": "fraud-v3.2"}`, optional)
  runs the sweep, persists it, returns the full result.
- `GET /decisions/{id}/forensic-sweeps` lists past sweeps for a decision (id, counts, timestamp).
- `GET /decisions/{id}/forensic-sweeps/{sweep_id}` returns one persisted sweep in full.

Persistence follows the same JSON-blob pattern as `DecisionRecord.context_json`
(see `docs/architecture.md`): a `ForensicSweepResult` is read/written as one atomic
frozen unit, because that is how it's actually used.

## Frontend

`frontend/src/views/ForensicSweep.tsx`, rendered inside Decision Forensics right below
Replay Lab. "RUN FORENSIC SWEEP" makes exactly one API call; the "checklist" shown after
it returns is a recap of real numbers read off that one response (experiment count,
critical/irrelevant/contributory counts, most-sensitive variable) -- not a simulated
progress bar, because there is no meaningful sub-progress to fake for a synchronous
in-memory computation. Clicking an experiment row opens its full detail: baseline vs.
counterfactual, boundary margins, governance impact, and an explicit limitation
disclaimer, worded the same way in every experiment view:

> Decision-critical under the replay model. This does not establish real-world causation.

## Static demo parity

The GitHub Pages build has no backend. `frontend/src/staticEngine.ts` ports
`generate_mutations`, `run_forensic_sweep`, `decision_sensitivity`, the boundary
calculation and a minimal `evaluate_controls` (the same three rules
`governance_engine.py` implements: `human_review_above_review_threshold`,
`approved_model_version`, `required_evidence_present`) into TypeScript, operating on the
`contexts[decision_id]` entry in `frontend/public/data/bundle.json`
(`backend/scripts/dump_static_bundle.py` now also dumps `tool_invocations` and
`control_definitions` per decision so the static engine has what it needs).
`frontend/scripts/parity_check.ts` (`bun run parity` from `frontend/`) asserts the
TypeScript sweep result for DEC-001 matches the Python golden values from
`backend/tests/test_sweep_engine.py` exactly -- same outcomes, same score deltas, same
causal statuses, same unsupported-type list. It fails loudly (non-zero exit) on any
mismatch; it is not a demo print.

## What this does not do

- It does not test multi-variable combinations automatically -- every auto-generated
  experiment is single-variable by construction, so no sweep experiment can ever be
  wrongly worded as `DECISION_CRITICAL` for more than one thing at once.
- It does not rank "feature importance" in the ML sense. `sensitivity` is a bounded
  distance-to-threshold measure of one specific mutation's effect on one specific score,
  nothing more.
- It does not claim real-world causation. Every `DECISION_CRITICAL` finding is scoped
  explicitly to "under the replay model" in both the API's `causal_explanation` field and
  the UI's limitation disclaimer.
