from app.golden_dataset import build_dec_001
from app.engines.replay_engine import replay, assess_replayability
from app.domain.enums import ReplayabilityStatus


def test_replay_matches_original_when_unmutated():
    d = build_dec_001()
    r = replay(d)
    assert r.outcome == d.decision
    assert abs(r.score - d.risk_score) < 1e-9


def test_replayability_is_full_for_golden_decision():
    d = build_dec_001()
    assessment = assess_replayability(d.context)
    assert assessment.status == ReplayabilityStatus.REPLAYABLE


def test_non_deterministic_tool_marks_partial_replayability():
    from dataclasses import replace
    d = build_dec_001()
    tools = tuple(replace(t, deterministic=False) if t.tool_id == "T2" else t
                   for t in d.context.tool_invocations)
    ctx = replace(d.context, tool_invocations=tools)
    assessment = assess_replayability(ctx)
    assert assessment.status == ReplayabilityStatus.PARTIALLY_REPLAYABLE


def test_missing_model_marks_non_replayable():
    from dataclasses import replace
    from app.domain.models import ModelVersion
    d = build_dec_001()
    ctx = replace(d.context, model_version=ModelVersion(model_id="", weights={}))
    assessment = assess_replayability(ctx)
    assert assessment.status == ReplayabilityStatus.NON_REPLAYABLE
