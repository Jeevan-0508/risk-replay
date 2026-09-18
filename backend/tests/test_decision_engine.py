from app.golden_dataset import build_dec_001
from app.engines.decision_engine import decide, score_context


def test_dec_001_blocks():
    d = build_dec_001()
    assert d.decision.value == "BLOCK"
    assert 0.0 <= d.risk_score <= 1.0


def test_score_breakdown_sums_to_raw_score():
    d = build_dec_001()
    breakdown = score_context(d.context)
    expected = breakdown.base_rate + sum(breakdown.contributions.values())
    assert abs(expected - breakdown.raw_score) < 1e-9


def test_decide_is_pure_function_of_context():
    d = build_dec_001()
    o1, s1, _ = decide(d.context)
    o2, s2, _ = decide(d.context)
    assert o1 == o2 and s1 == s2
