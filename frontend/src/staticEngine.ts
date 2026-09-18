/**
 * staticEngine.ts
 *
 * A faithful TypeScript port of the backend's decision/mutation/diff/causal
 * engines, used ONLY when the app is built for the static demo (GitHub Pages,
 * no backend). Same formulas, same wording, same non-negotiable rule: no LLM
 * anywhere in this file, every number traces to the line that produced it.
 * See backend/app/engines/*.py for the source of truth this mirrors.
 */

export interface StaticEvidence {
  evidence_id: string;
  kind: string;
  value: number;
  weight: number;
}

export interface StaticModelVersion {
  model_id: string;
  weights: Record<string, number>;
  base_rate: number;
}

export interface StaticPolicyVersion {
  policy_id: string;
  block_threshold: number;
  review_threshold: number;
}

export interface StaticToolInvocation {
  tool_id: string;
  tool_name: string;
  deterministic: boolean;
}

export interface StaticControlDefinition {
  control_id: string;
  name: string;
  rule: string;
}

export interface StaticContext {
  evidence: StaticEvidence[];
  model_version: StaticModelVersion;
  policy_version: StaticPolicyVersion;
  tool_invocations?: StaticToolInvocation[];
  control_definitions?: StaticControlDefinition[];
  human_override?: boolean;
}

export interface MutationDraft {
  type: string;
  target: string;
  reason: string;
  payload?: Record<string, unknown>;
}

export class MutationError extends Error {}

export function applyMutation(context: StaticContext, mutation: MutationDraft): StaticContext {
  if (mutation.type === "REMOVE_EVIDENCE") {
    const remaining = context.evidence.filter((e) => e.evidence_id !== mutation.target);
    if (remaining.length === context.evidence.length) {
      throw new MutationError(`Evidence '${mutation.target}' not found in context.`);
    }
    return { ...context, evidence: remaining };
  }
  if (mutation.type === "CHANGE_THRESHOLD") {
    const field = (mutation.payload?.field as string) || "block_threshold";
    const value = Number(mutation.payload?.value);
    if (Number.isNaN(value)) throw new MutationError("CHANGE_THRESHOLD requires a numeric 'value'.");
    return { ...context, policy_version: { ...context.policy_version, [field]: value } };
  }
  if (mutation.type === "REMOVE_TOOL_RESULT") {
    const tools = context.tool_invocations ?? [];
    const remaining = tools.filter((t) => t.tool_id !== mutation.target);
    if (remaining.length === tools.length) {
      throw new MutationError(`Tool invocation '${mutation.target}' not found in context.`);
    }
    return { ...context, tool_invocations: remaining };
  }
  if (mutation.type === "DISABLE_CONTROL") {
    const controls = context.control_definitions ?? [];
    const remaining = controls.filter((c) => c.control_id !== mutation.target);
    return { ...context, control_definitions: remaining };
  }
  throw new MutationError(`Unsupported mutation type in static demo: ${mutation.type}`);
}

export function applyMutations(context: StaticContext, mutations: MutationDraft[]): StaticContext {
  return mutations.reduce((ctx, m) => applyMutation(ctx, m), context);
}

export interface ScoringBreakdown {
  base_rate: number;
  contributions: Record<string, number>;
  raw_score: number;
  clamped_score: number;
}

/** score = base_rate + sum(evidence.value * weight), clamped to [0, 1]. */
export function scoreContext(context: StaticContext): ScoringBreakdown {
  const weights = context.model_version.weights;
  const contributions: Record<string, number> = {};
  let total = context.model_version.base_rate;
  for (const ev of context.evidence) {
    const w = weights[ev.kind] ?? ev.weight;
    const contribution = ev.value * w;
    contributions[ev.evidence_id] = contribution;
    total += contribution;
  }
  const clamped = Math.max(0, Math.min(1, total));
  return { base_rate: context.model_version.base_rate, contributions, raw_score: total, clamped_score: clamped };
}

/** BLOCK if score >= block_threshold, REVIEW if >= review_threshold, else ALLOW. */
export function decide(context: StaticContext): { outcome: string; score: number } {
  const breakdown = scoreContext(context);
  const score = breakdown.clamped_score;
  const policy = context.policy_version;
  let outcome: string;
  if (score >= policy.block_threshold) outcome = "BLOCK";
  else if (score >= policy.review_threshold) outcome = "REVIEW";
  else outcome = "ALLOW";
  return { outcome, score };
}

export interface DiffField {
  field: string;
  original: unknown;
  replay: unknown;
  changed: boolean;
}

export interface StaticCounterfactualResult {
  original_outcome: string;
  original_score: number;
  counterfactual_outcome: string;
  counterfactual_score: number;
  diverged: boolean;
  score_delta: number;
  causal_status: string;
  causal_explanation: string;
  is_multi_variable: boolean;
  diff_fields: DiffField[];
}

export function runCounterfactual(
  baselineContext: StaticContext,
  mutations: MutationDraft[]
): StaticCounterfactualResult {
  const original = decide(baselineContext);
  const mutatedContext = applyMutations(baselineContext, mutations);
  const replayed = decide(mutatedContext);

  const scoreDelta = Math.round((replayed.score - original.score) * 10000) / 10000;
  const diverged = original.outcome !== replayed.outcome;
  const isMultiVariable = mutations.length > 1;

  const diffFields: DiffField[] = [
    {
      field: "evidence_count",
      original: baselineContext.evidence.length,
      replay: mutatedContext.evidence.length,
      changed: baselineContext.evidence.length !== mutatedContext.evidence.length,
    },
    {
      field: "risk_score",
      original: Math.round(original.score * 10000) / 10000,
      replay: Math.round(replayed.score * 10000) / 10000,
      changed: Math.round(original.score * 10000) !== Math.round(replayed.score * 10000),
    },
    { field: "model", original: baselineContext.model_version.model_id, replay: "(see replay context)", changed: false },
    { field: "policy", original: baselineContext.policy_version.policy_id, replay: "(see replay context)", changed: false },
    { field: "decision", original: original.outcome, replay: replayed.outcome, changed: diverged },
  ];

  const mutationSummary = mutations.map((m) => `${m.type} on ${m.target}`).join("; ");

  let causalStatus: string;
  let causalExplanation: string;
  if (!diverged) {
    causalStatus = "DECISION_IRRELEVANT";
    causalExplanation = `Applying [${mutationSummary}] did not change the decision outcome under the replay model (score moved by ${scoreDelta}).`;
  } else if (!isMultiVariable) {
    causalStatus = "DECISION_CRITICAL";
    causalExplanation = `The decision changed from ${original.outcome} to ${replayed.outcome} solely because of [${mutationSummary}]. This variable is decision-critical under the replay model.`;
  } else {
    causalStatus = "CONTRIBUTORY";
    causalExplanation = `The decision changed from ${original.outcome} to ${replayed.outcome} after applying multiple mutations [${mutationSummary}]. Because more than one variable changed, no single variable can be isolated as decision-critical from this replay alone -- each would need its own single-variable counterfactual to confirm.`;
  }

  return {
    original_outcome: original.outcome,
    original_score: original.score,
    counterfactual_outcome: replayed.outcome,
    counterfactual_score: replayed.score,
    diverged,
    score_delta: scoreDelta,
    causal_status: causalStatus,
    causal_explanation: causalExplanation,
    is_multi_variable: isMultiVariable,
    diff_fields: diffFields,
  };
}

/**
 * FORENSIC SWEEP -- TypeScript port of backend/app/engines/sweep_engine.py.
 * Mirrors the same rule: auto-generate one single-variable REMOVE_EVIDENCE /
 * REMOVE_TOOL_RESULT / DISABLE_CONTROL experiment per item that already
 * exists in the recorded context. Never fabricates a hypothetical value for
 * CHANGE_POLICY / CHANGE_MODEL / CHANGE_THRESHOLD / etc -- those are reported
 * as unsupported-for-auto-sweep, same as the backend. See
 * docs/forensic-sweep.md for the full rationale (shared by both engines).
 */

export interface GovernanceFindingLite {
  control_id: string;
  control_name: string;
  status: string; // "SATISFIED" | "FAILED" | "NOT_APPLICABLE"
  reason: string;
}

/** Minimal port of governance_engine.evaluate_controls -- same three rules. */
export function evaluateControls(context: StaticContext, riskScore: number, humanOverride: boolean, approvedModelIds: Set<string>): GovernanceFindingLite[] {
  const controls = context.control_definitions ?? [];
  const findings: GovernanceFindingLite[] = [];
  for (const control of controls) {
    if (control.rule === "human_review_above_review_threshold") {
      const crossed = riskScore >= context.policy_version.review_threshold;
      if (crossed && !humanOverride) {
        findings.push({ control_id: control.control_id, control_name: control.name, status: "FAILED",
          reason: `Decision crossed the configured review threshold (${context.policy_version.review_threshold}) but no human override/review was recorded.` });
      } else {
        findings.push({ control_id: control.control_id, control_name: control.name, status: "SATISFIED",
          reason: "Review threshold not crossed, or human override present." });
      }
    } else if (control.rule === "approved_model_version") {
      const ok = approvedModelIds.size === 0 || approvedModelIds.has(context.model_version.model_id);
      findings.push({ control_id: control.control_id, control_name: control.name,
        status: ok ? "SATISFIED" : "FAILED",
        reason: ok ? "Model version is on the approved list." : `Model version ${context.model_version.model_id} is not on the approved list.` });
    } else {
      findings.push({ control_id: control.control_id, control_name: control.name, status: "NOT_APPLICABLE",
        reason: `Unknown control rule '${control.rule}'; not evaluated.` });
    }
  }
  return findings;
}

export interface ForensicExperimentLite {
  experiment_id: string;
  variable: string;
  variable_kind: string;
  mutation_type: string;
  mutation_summary: string;
  baseline_outcome: string;
  baseline_score: number;
  counterfactual_outcome: string;
  counterfactual_score: number;
  score_delta: number;
  diverged: boolean;
  causal_status: string;
  causal_explanation: string;
  sensitivity: number;
  boundary: Record<string, unknown>;
  governance_impact: { control_id: string; control_name: string; before_status: string; after_status: string; changed: boolean }[];
}

export interface ForensicSweepResultLite {
  sweep_id: string;
  decision_id: string;
  baseline_outcome: string;
  baseline_score: number;
  experiments: ForensicExperimentLite[];
  unsupported_mutation_types: { mutation_type: string; reason: string }[];
  summary: {
    experiment_count: number;
    decision_critical_count: number;
    decision_irrelevant_count: number;
    contributory_count: number;
    non_replayable_count: number;
    most_sensitive_variable: string | null;
    divergence_ratio: number;
  };
}

const UNSUPPORTED_REASONS: Record<string, string> = {
  CHANGE_POLICY: "Requires a hypothetical replacement PolicyVersion not present in the historical record.",
  CHANGE_MODEL: "Requires a hypothetical replacement ModelVersion not present in the historical record.",
  CHANGE_THRESHOLD: "Requires an arbitrary new threshold value; no canonical value to test without fabricating one.",
  ADD_EVIDENCE: "Requires fabricating evidence that was never recorded for this decision.",
  MODIFY_EVIDENCE: "Requires an arbitrary replacement value for an existing evidence item.",
  MODIFY_TOOL_RESULT: "Requires an arbitrary replacement tool output; no canonical alternative to test.",
  CHANGE_INPUT: "Requires an arbitrary replacement input payload; no canonical alternative to test.",
};

export function generateMutationsStatic(context: StaticContext, _decisionId: string): MutationDraft[] {
  const mutations: MutationDraft[] = [];
  let seq = 0;
  for (const ev of context.evidence) {
    seq += 1;
    mutations.push({ type: "REMOVE_EVIDENCE", target: ev.evidence_id, reason: "Forensic sweep: single-variable test of evidence contribution." });
  }
  for (const tool of context.tool_invocations ?? []) {
    seq += 1;
    mutations.push({ type: "REMOVE_TOOL_RESULT", target: tool.tool_id, reason: "Forensic sweep: single-variable test of tool-result contribution." });
  }
  for (const control of context.control_definitions ?? []) {
    seq += 1;
    mutations.push({ type: "DISABLE_CONTROL", target: control.control_id, reason: "Forensic sweep: single-variable test of control contribution." });
  }
  return mutations;
}

function variableKind(mutationType: string): string {
  if (mutationType === "REMOVE_EVIDENCE") return "evidence";
  if (mutationType === "REMOVE_TOOL_RESULT") return "tool_invocation";
  return "control";
}

/** Same formula as diff_engine.decision_sensitivity: min(1, |delta| / block_threshold). */
export function decisionSensitivity(originalScore: number, mutatedScore: number, blockThreshold: number): number {
  if (blockThreshold <= 0) return 0.0;
  const delta = Math.abs(mutatedScore - originalScore);
  return Math.round(Math.min(1, delta / blockThreshold) * 10000) / 10000;
}

function boundary(baselineScore: number, cfScore: number, blockThreshold: number, reviewThreshold: number) {
  return {
    baseline_margin_to_block_threshold: Math.round((blockThreshold - baselineScore) * 10000) / 10000,
    baseline_margin_to_review_threshold: Math.round((reviewThreshold - baselineScore) * 10000) / 10000,
    counterfactual_margin_to_block_threshold: Math.round((blockThreshold - cfScore) * 10000) / 10000,
    counterfactual_margin_to_review_threshold: Math.round((reviewThreshold - cfScore) * 10000) / 10000,
    crossed_block_threshold: (baselineScore >= blockThreshold) !== (cfScore >= blockThreshold),
    crossed_review_threshold: (baselineScore >= reviewThreshold) !== (cfScore >= reviewThreshold),
    direction: cfScore < baselineScore ? "decrease" : cfScore > baselineScore ? "increase" : "none",
  };
}

export function runForensicSweepStatic(context: StaticContext, decisionId: string, approvedModelIds: Set<string>): ForensicSweepResultLite {
  const sweepId = `SWEEP-${decisionId}`;
  const policy = context.policy_version;
  const humanOverride = context.human_override ?? false;
  const baseline = decide(context);
  const baselineGovernance = evaluateControls(context, baseline.score, humanOverride, approvedModelIds);

  const mutations = generateMutationsStatic(context, decisionId);
  const experiments: ForensicExperimentLite[] = mutations.map((mutation, i) => {
    const cf = runCounterfactual(context, [mutation]);
    const mutatedContext = applyMutation(context, mutation);
    const afterGovernance = evaluateControls(mutatedContext, cf.counterfactual_score, humanOverride, approvedModelIds);
    const afterById: Record<string, GovernanceFindingLite> = {};
    for (const f of afterGovernance) afterById[f.control_id] = f;
    const governanceImpact = baselineGovernance.map((f) => {
      const after = afterById[f.control_id];
      return {
        control_id: f.control_id, control_name: f.control_name,
        before_status: f.status, after_status: after ? after.status : "NOT_APPLICABLE",
        changed: !!after && after.status !== f.status,
      };
    });
    return {
      experiment_id: `${sweepId}-${String(i + 1).padStart(3, "0")}`,
      variable: mutation.target,
      variable_kind: variableKind(mutation.type),
      mutation_type: mutation.type,
      mutation_summary: `${mutation.type} on ${mutation.target}`,
      baseline_outcome: cf.original_outcome,
      baseline_score: Math.round(cf.original_score * 10000) / 10000,
      counterfactual_outcome: cf.counterfactual_outcome,
      counterfactual_score: Math.round(cf.counterfactual_score * 10000) / 10000,
      score_delta: cf.score_delta,
      diverged: cf.diverged,
      causal_status: cf.causal_status,
      causal_explanation: cf.causal_explanation,
      sensitivity: decisionSensitivity(cf.original_score, cf.counterfactual_score, policy.block_threshold),
      boundary: boundary(cf.original_score, cf.counterfactual_score, policy.block_threshold, policy.review_threshold),
      governance_impact: governanceImpact,
    };
  });

  const unsupported = Object.entries(UNSUPPORTED_REASONS).map(([mutation_type, reason]) => ({ mutation_type, reason }));

  const count = experiments.length;
  const critical = experiments.filter((e) => e.causal_status === "DECISION_CRITICAL").length;
  const irrelevant = experiments.filter((e) => e.causal_status === "DECISION_IRRELEVANT").length;
  const contributory = experiments.filter((e) => e.causal_status === "CONTRIBUTORY").length;
  const nonReplayable = experiments.filter((e) => e.causal_status === "NON_REPLAYABLE").length;
  const diverged = experiments.filter((e) => e.diverged).length;
  let mostSensitive: string | null = null;
  if (experiments.length > 0) {
    mostSensitive = experiments.reduce((best, e) => (e.sensitivity > best.sensitivity ? e : best), experiments[0]).variable;
  }

  return {
    sweep_id: sweepId,
    decision_id: decisionId,
    baseline_outcome: baseline.outcome,
    baseline_score: Math.round(baseline.score * 10000) / 10000,
    experiments,
    unsupported_mutation_types: unsupported,
    summary: {
      experiment_count: count,
      decision_critical_count: critical,
      decision_irrelevant_count: irrelevant,
      contributory_count: contributory,
      non_replayable_count: nonReplayable,
      most_sensitive_variable: mostSensitive,
      divergence_ratio: count > 0 ? Math.round((diverged / count) * 10000) / 10000 : 0,
    },
  };
}
