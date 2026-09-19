/**
 * frontend/scripts/parity_check.ts
 *
 * Proves TypeScript result == Python result for the Forensic Sweep on the
 * golden DEC-001 case (see backend/app/golden_dataset.py and
 * backend/tests/test_sweep_engine.py for the Python-side assertions this
 * mirrors). Run with: `bun run scripts/parity_check.ts` from frontend/.
 * Exits non-zero on any mismatch -- this is a real check, not a demo print.
 */
import { runForensicSweepStatic, analyzeBoundary, buildDnaStatic } from "../src/staticEngine";
import bundle from "../public/data/bundle.json";

const ctx = (bundle as any).contexts["DEC-001"];
const result = runForensicSweepStatic(ctx, "DEC-001", new Set(["fraud-v3.2"]));

const expected: [string, string, string, number, string][] = [
  ["E1", "REMOVE_EVIDENCE", "REVIEW", -0.225, "DECISION_CRITICAL"],
  ["E2", "REMOVE_EVIDENCE", "REVIEW", -0.154, "DECISION_CRITICAL"],
  ["E3", "REMOVE_EVIDENCE", "ALLOW", -0.285, "DECISION_CRITICAL"],
  ["E4", "REMOVE_EVIDENCE", "REVIEW", -0.12, "DECISION_CRITICAL"],
  ["T1", "REMOVE_TOOL_RESULT", "BLOCK", 0, "DECISION_IRRELEVANT"],
  ["T2", "REMOVE_TOOL_RESULT", "BLOCK", 0, "DECISION_IRRELEVANT"],
  ["T3", "REMOVE_TOOL_RESULT", "BLOCK", 0, "DECISION_IRRELEVANT"],
  ["C-17", "DISABLE_CONTROL", "BLOCK", 0, "DECISION_IRRELEVANT"],
  ["C-08", "DISABLE_CONTROL", "BLOCK", 0, "DECISION_IRRELEVANT"],
];

let failures = 0;

function check(label: string, actual: unknown, wanted: unknown) {
  if (actual !== wanted) {
    console.error(`MISMATCH ${label}: got ${JSON.stringify(actual)}, wanted ${JSON.stringify(wanted)}`);
    failures++;
  }
}

check("baseline_outcome", result.baseline_outcome, "BLOCK");
check("baseline_score", result.baseline_score, 0.834);
check("experiment_count", result.experiments.length, expected.length);

for (const [variable, mutationType, outcome, delta, causal] of expected) {
  const exp = result.experiments.find((e) => e.variable === variable && e.mutation_type === mutationType);
  if (!exp) {
    console.error(`MISMATCH: no experiment found for ${variable}/${mutationType}`);
    failures++;
    continue;
  }
  check(`${variable}.counterfactual_outcome`, exp.counterfactual_outcome, outcome);
  check(`${variable}.score_delta`, exp.score_delta, delta);
  check(`${variable}.causal_status`, exp.causal_status, causal);
}

check("summary.most_sensitive_variable", result.summary.most_sensitive_variable, "E3");
check("summary.decision_critical_count", result.summary.decision_critical_count, 4);
check("summary.decision_irrelevant_count", result.summary.decision_irrelevant_count, 5);
check("summary.divergence_ratio", result.summary.divergence_ratio, 0.4444);

const unsupportedTypes = new Set(result.unsupported_mutation_types.map((u) => u.mutation_type));
for (const t of ["CHANGE_POLICY", "CHANGE_MODEL", "CHANGE_THRESHOLD", "ADD_EVIDENCE", "MODIFY_EVIDENCE", "MODIFY_TOOL_RESULT", "CHANGE_INPUT"]) {
  if (!unsupportedTypes.has(t)) {
    console.error(`MISMATCH: expected ${t} to be reported as unsupported-for-auto-sweep`);
    failures++;
  }
}


// --- Decision Boundary Analyzer parity (backend/app/engines/boundary_engine.py) ---
const boundaryProfile = analyzeBoundary(0.834, ctx.policy_version.block_threshold, ctx.policy_version.review_threshold);
check("boundary.zone", boundaryProfile.zone, "BLOCK");
check("boundary.distance_to_block_threshold", boundaryProfile.distance_to_block_threshold, -0.014);
check("boundary.distance_to_review_threshold", boundaryProfile.distance_to_review_threshold, -0.284);

// --- Decision DNA parity (backend/app/engines/dna_engine.py) ---
const dna = buildDnaStatic(ctx, "DEC-001", 0.834, "BLOCK", "REPLAYABLE", result as any);
check("dna.model", dna.model, "fraud-v3.2");
check("dna.policy", dna.policy, "policy-17");
check("dna.zone", dna.zone, "BLOCK");
check("dna.integrity_status", dna.integrity_status, "VERIFIED");
check("dna.evidence_count", dna.evidence_count, 4);
check("dna.decision_critical_variables", JSON.stringify([...dna.decision_critical_variables!].sort()), JSON.stringify(["E1", "E2", "E3", "E4"]));
check("dna.governance_affected_controls", JSON.stringify(dna.governance_affected_controls), JSON.stringify(["C-17"]));

if (failures > 0) {
  console.error(`\nPARITY CHECK FAILED: ${failures} mismatch(es) between TS and Python golden values.`);
  process.exit(1);
} else {
  console.log("PARITY CHECK PASSED: TypeScript Forensic Sweep, Boundary Analyzer and Decision DNA all match the Python golden values exactly.");
}
