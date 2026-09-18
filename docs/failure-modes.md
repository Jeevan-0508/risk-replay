# Failure Modes: Non-Replayability

A forensic tool that always produces a confident answer is not trustworthy. RISK//REPLAY
treats "we cannot reconstruct this" as a first-class, explicit output.

## Reasons (`NonReplayableReason`)

`MISSING_INPUT`, `MISSING_EVIDENCE`, `MISSING_MODEL_VERSION`, `MISSING_POLICY_VERSION`,
`NON_DETERMINISTIC_TOOL`, `EXTERNAL_STATE_CHANGED`, `PROVENANCE_GAP`,
`UNKNOWN_DEPENDENCY`.

## What actually gates each status

- Missing input snapshot hash, missing model version id, or missing policy version id
  -> `NON_REPLAYABLE`. These are the three things `decide()` cannot run without.
- A non-deterministic tool invocation, or an evidence item without a content hash
  (provenance gap) -> `PARTIALLY_REPLAYABLE`. The replay still runs and produces a
  result, but that result carries the caveat.
- Nothing missing -> `REPLAYABLE`.

See `app/engines/replay_engine.py::assess_replayability()` for the exact logic, and
`tests/test_replay_engine.py` for the three states each independently tested.

## Currently NOT implemented (honest gap)

`EXTERNAL_STATE_CHANGED` and `UNKNOWN_DEPENDENCY` exist in the enum but nothing in the
engine currently detects them -- there's no "external state" concept modeled yet (e.g.
a tool that calls a live currency-conversion rate that could have changed since the
decision). Adding that requires deciding how a `ToolInvocation` records the volatility
class of what it queried, which is a real design decision, not a one-line fix -- flagged
here rather than silently claimed as done.

## Forensic Sweep and non-replayability

Each sweep experiment carries its own `replayability_status`/`replayability_reasons`, taken directly from that experiment's counterfactual replay -- a missing model id, missing policy id, or non-deterministic tool anywhere in the context still produces an explicit `NON_REPLAYABLE`/`PARTIALLY_REPLAYABLE` status per experiment, never a silently fabricated result. See `test_missing_model_id_yields_non_replayable_not_a_fabricated_result` and `test_non_deterministic_tool_removal_still_yields_explicit_replayability_status` in `backend/tests/test_sweep_engine.py`.
