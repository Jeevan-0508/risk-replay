# Risk Engine -- Formulas

All defined in `app/engines/risk_engine.py::assess_risk()`. Every metric below is
returned to the API caller alongside a `formulas` dict explaining it in the same call
(`GET /decisions/{id}/risk`) -- nothing here is a hidden number.

| Metric | Formula |
|---|---|
| `decision_risk` | the `risk_score` computed by `decision_engine.decide()` at decision time (0..1) |
| `evidence_completeness` | `count(evidence with content_hash) / count(evidence)` |
| `provenance_completeness` | `count(provenance items with content_hash) / count(all provenance items)` (evidence + input snapshot) |
| `control_coverage` | `count(required_controls actually evaluated) / count(required_controls)` |
| `policy_violation_count` | `count(controls where status == FAILED)` |
| `replay_divergence` | `1.0` if a counterfactual's outcome != original outcome, else `0.0` (only present once a counterfactual has been run) |
| `decision_sensitivity` | `min(1, abs(score_delta) / policy.block_threshold)` -- how much of the "distance to the block boundary" a mutation consumed |
| `risk_level` | banded from `decision_risk`: `>=0.85` CRITICAL, `>=0.6` HIGH, `>=0.3` MEDIUM, else LOW |

## Blast radius

`blast_radius(decisions, counterfactual_results)` in the same module aggregates:
`affected_decisions`, `decision_changes`, `human_review_changes`
(counterfactual outcome == `REVIEW`), `high_risk_changes` (`abs(score_delta) >= 0.2`),
`no_change`. Used by `/incidents/{id}/blast-radius` and the policy-impact-replay
endpoint.
