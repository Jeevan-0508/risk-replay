"""
backend/app/engines/boundary_engine.py

DECISION BOUNDARY ANALYZER: a pure, deterministic engine that explains a
score's position relative to a policy's block/review thresholds, and -- for
a pair of scores (e.g. baseline vs. counterfactual) -- which boundary was
crossed and in which direction.

This is the single source of truth for boundary math. sweep_engine and any
future caller (manual counterfactuals, policy-impact-replay) must call this
module rather than re-deriving the arithmetic, so there is exactly one
formula to test and one place to fix if it is ever wrong.

Zone model (matches decision_engine.decide()):
    score >= block_threshold                         -> BLOCK
    review_threshold <= score < block_threshold       -> REVIEW
    score < review_threshold                          -> ALLOW

Guarantee and non-guarantee:
    This module tells you WHICH threshold was crossed between two scores.
    It does NOT tell you why the score changed, and it does NOT establish
    real-world causation -- that scoping lives in causal_engine and in
    docs/methodology.md.
"""
from __future__ import annotations

from dataclasses import dataclass


def _zone(score: float, block_threshold: float, review_threshold: float) -> str:
    if score >= block_threshold:
        return "BLOCK"
    if score >= review_threshold:
        return "REVIEW"
    return "ALLOW"


@dataclass(frozen=True)
class BoundaryProfile:
    """Where a single score sits relative to a policy's thresholds."""

    score: float
    block_threshold: float
    review_threshold: float
    zone: str
    distance_to_block_threshold: float
    distance_to_review_threshold: float

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "block_threshold": self.block_threshold,
            "review_threshold": self.review_threshold,
            "zone": self.zone,
            "distance_to_block_threshold": self.distance_to_block_threshold,
            "distance_to_review_threshold": self.distance_to_review_threshold,
        }


@dataclass(frozen=True)
class BoundaryTransition:
    """What changed between a baseline score and a counterfactual score."""

    baseline: BoundaryProfile
    counterfactual: BoundaryProfile
    crossed_block_threshold: bool
    crossed_review_threshold: bool
    transition: str  # e.g. "BLOCK->ALLOW", "REVIEW->REVIEW" (no change)

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict(),
            "counterfactual": self.counterfactual.to_dict(),
            "crossed_block_threshold": self.crossed_block_threshold,
            "crossed_review_threshold": self.crossed_review_threshold,
            "transition": self.transition,
        }


def analyze(score: float, block_threshold: float, review_threshold: float) -> BoundaryProfile:
    """Where does `score` sit relative to the two thresholds, and how far is it from each?"""
    score = max(0.0, min(1.0, score))
    zone = _zone(score, block_threshold, review_threshold)
    return BoundaryProfile(
        score=round(score, 4),
        block_threshold=round(block_threshold, 4),
        review_threshold=round(review_threshold, 4),
        zone=zone,
        distance_to_block_threshold=round(block_threshold - score, 4),
        distance_to_review_threshold=round(review_threshold - score, 4),
    )


def compare(
    baseline_score: float,
    counterfactual_score: float,
    block_threshold: float,
    review_threshold: float,
) -> BoundaryTransition:
    """Compare two scores against the same pair of thresholds and explain the transition."""
    baseline = analyze(baseline_score, block_threshold, review_threshold)
    counterfactual = analyze(counterfactual_score, block_threshold, review_threshold)
    crossed_block = (baseline.score >= block_threshold) != (counterfactual.score >= block_threshold)
    crossed_review = (baseline.score >= review_threshold) != (counterfactual.score >= review_threshold)
    transition = f"{baseline.zone}->{counterfactual.zone}"
    return BoundaryTransition(
        baseline=baseline,
        counterfactual=counterfactual,
        crossed_block_threshold=crossed_block,
        crossed_review_threshold=crossed_review,
        transition=transition,
    )
