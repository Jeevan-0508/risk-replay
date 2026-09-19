# Decision Boundary Analyzer

## What it is

A pure, deterministic engine (`backend/app/engines/boundary_engine.py`) that
explains a score's position relative to a policy's `block_threshold` and
`review_threshold`, and -- given two scores -- which boundary was crossed
and in which direction.

It replaces ad-hoc "diverged=true" reporting with an explicit answer to:
*which* boundary moved, and *which way*.

## Zone model

Matches `decision_engine.decide()` exactly:

```
score >= block_threshold                      -> BLOCK
review_threshold <= score < block_threshold    -> REVIEW
score < review_threshold                       -> ALLOW
```

## API

- `analyze(score, block_threshold, review_threshold) -> BoundaryProfile`
  Where does one score sit? Zone, and signed distance to each threshold
  (`block_threshold - score`; negative means the score is past that
  threshold already).
- `compare(baseline_score, counterfactual_score, block_threshold,
  review_threshold) -> BoundaryTransition`
  Compares two scores against the same thresholds. Reports
  `crossed_block_threshold`, `crossed_review_threshold`, and a
  human-readable `transition` string such as `"BLOCK->ALLOW"`.

## Where it's used

- `sweep_engine._boundary()` delegates to `boundary_engine.compare()` for
  every Forensic Sweep experiment (no duplicated arithmetic).
- `dna_engine.build_dna()` calls `boundary_engine.analyze()` to compute
  `boundary_margin` and `zone`.
- `GET /decisions/{id}/boundary` exposes a standalone profile for the
  current decision.

## What it does not do

It tells you *which* threshold was crossed between two scores. It does not
explain *why* the underlying score changed (that's `causal_engine`'s
scoped, replay-only wording) and it does not establish real-world
causation -- see `docs/methodology.md`.

## Tests

`backend/tests/test_boundary_engine.py` (15 tests): zone boundaries at
exact/just-above/just-below threshold values, all three transition types
(BLOCK->REVIEW, REVIEW->ALLOW, BLOCK->ALLOW), no-change same-zone case,
score clamping to [0,1], and independent multi-threshold policies.
