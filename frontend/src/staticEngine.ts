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

export interface StaticContext {
  evidence: StaticEvidence[];
  model_version: StaticModelVersion;
  policy_version: StaticPolicyVersion;
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
