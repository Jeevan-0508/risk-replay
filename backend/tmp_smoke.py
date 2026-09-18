import sys
sys.path.insert(0, ".")
from app.golden_dataset import build_dec_001
from app.engines.replay_engine import replay
from app.engines.mutation_engine import Mutation
from app.domain.enums import MutationType
from app.engines.counterfactual_engine import run_counterfactual
from app.engines.causal_engine import analyze
from app.engines.risk_engine import assess_risk
from app.engines.governance_engine import evaluate_controls

d = build_dec_001()
print("Original decision:", d.decision.value, "score:", round(d.risk_score,4))
assert d.decision.value == "BLOCK", "demo assumption broken: DEC-001 should BLOCK"

baseline_replay = replay(d)
print("Baseline replay matches original:", baseline_replay.outcome == d.decision, baseline_replay.outcome.value)
assert baseline_replay.outcome == d.decision

m = Mutation(mutation_id="M1", type=MutationType.REMOVE_EVIDENCE, target="E3", before="present", after="absent", reason="test removal")
cf = run_counterfactual(d, [m])
print("Counterfactual outcome:", cf.counterfactual_replay.outcome.value, "score:", round(cf.counterfactual_replay.score,4))
print("Diverged:", cf.diff.diverged)
assert cf.counterfactual_replay.outcome.value == "ALLOW", f"expected ALLOW got {cf.counterfactual_replay.outcome.value}"
assert cf.diff.diverged

finding = analyze(cf)
print("Causal finding:", finding.status.value)
print(finding.explanation)
assert finding.status.value == "DECISION_CRITICAL"

risk = assess_risk(d, cf)
print("Risk assessment:", risk.risk_level.value, risk.decision_risk)

gov = evaluate_controls(d, approved_model_ids={"fraud-v3.2"})
for f in gov:
    print("Governance:", f.control_id, f.status.value, "-", f.reason)

print("\nALL SMOKE CHECKS PASSED")
