# Replay Model

## What "deterministic replay" means here

Given the same `DecisionContext` (input snapshot, evidence, model version, policy
version, tool invocations), `decision_engine.decide()` always produces the same
outcome and score. This is trivially true because the scoring function is a pure
weighted sum with no randomness and no external calls -- see
`app/engines/decision_engine.py`.

## What replay does NOT do

A replay never re-runs a tool, never re-queries a live service, and never substitutes
"whatever the current production model/policy is" for a missing historical version.
If the context is incomplete, `assess_replayability()` reports exactly why
(`MISSING_MODEL_VERSION`, `NON_DETERMINISTIC_TOOL`, etc.) instead of silently filling
the gap. See `docs/failure-modes.md`.

## Replayability status

| Status | Meaning |
|---|---|
| `REPLAYABLE` | All required context present, all tool outputs marked deterministic. |
| `PARTIALLY_REPLAYABLE` | Context present but contains a non-deterministic tool output or a provenance gap on non-blocking data. Replay runs, but its result should be read with that caveat attached. |
| `NON_REPLAYABLE` | Input, model version, or policy version missing. The engine still computes a score for transparency, but the result is not evidence of anything. |

## Limits of this v1 model

The scoring function is an explicit weighted sum, not a stand-in for a real ML model's
internal computation. This is intentional for a v1 forensic engine: it keeps every
score legible and testable. Replaying a decision from a real gradient-boosted or neural
model would require snapshotting the model artifact itself (weights + architecture) and
running actual inference at the recorded version -- a real system would plug that in
behind the same `ModelVersion` / `decide()` seam without changing anything upstream.
