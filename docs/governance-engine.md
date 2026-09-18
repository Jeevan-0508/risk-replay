# Governance Engine

Every control evaluation in `app/engines/governance_engine.py::evaluate_controls()` is
a pure function of the `DecisionContext` plus, where relevant, an externally-supplied
allow-list (e.g. approved model versions) -- never an LLM judgment call.

## Implemented control rules

- `human_review_above_review_threshold`: FAILS if `risk_score >= policy.review_threshold`
  and no `HumanOverride` is recorded on the decision.
- `approved_model_version`: FAILS if `model_version.model_id` is not in the caller-supplied
  approved set.
- `required_evidence_present`: FAILS if any evidence "kind" listed in the control's
  description is missing from the context's evidence set.

Unknown rule names resolve to `NOT_APPLICABLE` rather than being silently skipped or
guessed at.

## Adding a new control

Add a `ControlDefinition(control_id, name, description, rule)` to a `DecisionContext`,
then add a branch to `evaluate_controls()` for the new `rule` string. No changes needed
elsewhere -- the API, risk engine, and diff engine all consume `ControlEvaluation`
objects generically.
