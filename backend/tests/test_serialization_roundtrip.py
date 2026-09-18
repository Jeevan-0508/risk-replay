from app.golden_dataset import build_dec_001
from app.db.serialization import context_to_dict, context_from_dict, decision_to_record_fields, record_to_decision
from app.engines.decision_engine import decide


class _FakeRecord:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_context_roundtrip_preserves_decision():
    d = build_dec_001()
    as_dict = context_to_dict(d.context)
    restored_ctx = context_from_dict(as_dict)
    outcome, score, _ = decide(restored_ctx)
    assert outcome == d.decision
    assert abs(score - d.risk_score) < 1e-9
    assert restored_ctx.context_hash() == d.context.context_hash()


def test_decision_record_roundtrip():
    d = build_dec_001()
    fields = decision_to_record_fields(d)
    record = _FakeRecord(**fields)
    restored = record_to_decision(record)
    assert restored.decision_id == d.decision_id
    assert restored.decision == d.decision
    assert abs(restored.risk_score - d.risk_score) < 1e-9
    assert restored.context.context_hash() == d.context.context_hash()
