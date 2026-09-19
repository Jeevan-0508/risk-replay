"""Tests for app.engines.boundary_engine -- the Decision Boundary Analyzer."""
from app.engines import boundary_engine


def test_analyze_block_zone():
    p = boundary_engine.analyze(0.834, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "BLOCK"
    assert p.distance_to_block_threshold == round(0.82 - 0.834, 4)


def test_analyze_review_zone():
    p = boundary_engine.analyze(0.6, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "REVIEW"


def test_analyze_allow_zone():
    p = boundary_engine.analyze(0.2, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "ALLOW"


def test_exact_block_threshold_is_block():
    # score == block_threshold: decision_engine treats >= as BLOCK, boundary
    # analyzer must agree exactly, not be off by an epsilon.
    p = boundary_engine.analyze(0.82, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "BLOCK"


def test_exact_review_threshold_is_review():
    p = boundary_engine.analyze(0.55, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "REVIEW"


def test_just_above_block_threshold():
    p = boundary_engine.analyze(0.8201, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "BLOCK"


def test_just_below_block_threshold():
    p = boundary_engine.analyze(0.8199, block_threshold=0.82, review_threshold=0.55)
    assert p.zone == "REVIEW"


def test_score_clamping_above_one():
    p = boundary_engine.analyze(1.5, block_threshold=0.82, review_threshold=0.55)
    assert p.score == 1.0


def test_score_clamping_below_zero():
    p = boundary_engine.analyze(-0.3, block_threshold=0.82, review_threshold=0.55)
    assert p.score == 0.0


def test_compare_block_to_allow():
    t = boundary_engine.compare(0.834, 0.2, block_threshold=0.82, review_threshold=0.55)
    assert t.transition == "BLOCK->ALLOW"
    assert t.crossed_block_threshold is True
    assert t.crossed_review_threshold is True


def test_compare_block_to_review():
    t = boundary_engine.compare(0.834, 0.6, block_threshold=0.82, review_threshold=0.55)
    assert t.transition == "BLOCK->REVIEW"
    assert t.crossed_block_threshold is True
    assert t.crossed_review_threshold is False


def test_compare_review_to_allow():
    t = boundary_engine.compare(0.6, 0.2, block_threshold=0.82, review_threshold=0.55)
    assert t.transition == "REVIEW->ALLOW"
    assert t.crossed_block_threshold is False
    assert t.crossed_review_threshold is True


def test_compare_no_change_same_zone():
    t = boundary_engine.compare(0.834, 0.9, block_threshold=0.82, review_threshold=0.55)
    assert t.transition == "BLOCK->BLOCK"
    assert t.crossed_block_threshold is False
    assert t.crossed_review_threshold is False


def test_compare_multiple_thresholds_independent():
    # A different policy's thresholds must be used as given, not hardcoded.
    t = boundary_engine.compare(0.5, 0.1, block_threshold=0.6, review_threshold=0.3)
    assert t.transition == "REVIEW->ALLOW"


def test_to_dict_round_trip_has_expected_keys():
    t = boundary_engine.compare(0.834, 0.2, block_threshold=0.82, review_threshold=0.55)
    d = t.to_dict()
    assert set(d.keys()) == {
        "baseline", "counterfactual", "crossed_block_threshold",
        "crossed_review_threshold", "transition",
    }
    assert set(d["baseline"].keys()) == {
        "score", "block_threshold", "review_threshold", "zone",
        "distance_to_block_threshold", "distance_to_review_threshold",
    }
