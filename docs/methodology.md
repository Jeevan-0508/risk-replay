# Methodology: Causal Language

RISK//REPLAY never claims real-world causal certainty from a replay. It claims exactly
what the replay demonstrated, scoped to "under the replay model."

| Status | When it's used |
|---|---|
| `DECISION_CRITICAL` | A single-variable mutation flipped the outcome. The variable was necessary for this outcome under this replay. |
| `DECISION_IRRELEVANT` | The mutation did not change the outcome. |
| `CONTRIBUTORY` | Multiple variables changed at once and the outcome flipped -- no single variable can be isolated from this run alone. |
| `NON_DETERMINATIVE` | Reserved for cases where a mutation changes the score but not the outcome band (not yet surfaced by the causal engine -- see Deferred below). |
| `INSUFFICIENT_EVIDENCE` | Reserved for cases where too little of the context is available to reason about at all. |
| `NON_REPLAYABLE` | Baseline or counterfactual replay itself was `NON_REPLAYABLE` -- no causal claim is made. |

We deliberately do not say "E3 is the true cause of the block." We say: removing E3
changed BLOCK to ALLOW, and no other variable changed. That is what a single-variable
counterfactual replay can actually prove, and it's a materially useful finding without
overclaiming.

**Deferred**: `NON_DETERMINATIVE` and `INSUFFICIENT_EVIDENCE` are defined in the enum
and this doc for completeness of the status vocabulary, but `causal_engine.analyze()`
does not yet emit them -- today it only distinguishes
critical/irrelevant/contributory/non-replayable. Extending it is a small, contained
change once a concrete scenario needs the finer distinction.
