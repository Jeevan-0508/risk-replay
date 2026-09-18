const API_BASE = (import.meta as any).env?.VITE_API_BASE || "http://127.0.0.1:8000";

async function req<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export interface DecisionSummary {
  decision_id: string;
  system: string;
  timestamp: string;
  model_id: string;
  policy_id: string;
  decision: string;
  final_outcome: string;
  confidence: number;
  risk_score: number;
  evidence_count: number;
  incident_id: string | null;
}

export interface EvidenceOut {
  evidence_id: string;
  source: string;
  kind: string;
  value: number;
  weight: number;
  classification: string;
  retrieved_by: string | null;
  content_hash: string;
}

export interface DecisionDetail extends DecisionSummary {
  evidence: EvidenceOut[];
  controls: { control_id: string; status: string; reason: string }[];
  tool_invocations: { tool_id: string; tool_name: string; output: Record<string, unknown>; deterministic: boolean }[];
  context_hash: string;
  replayability_status: string;
  replayability_reasons: string[];
}

export interface LineageGraph {
  nodes: { id: string; type: string; label: string }[];
  edges: { from: string; to: string; type: string }[];
}

export interface CounterfactualOut {
  counterfactual_id: string;
  decision_id: string;
  original_outcome: string;
  original_score: number;
  counterfactual_outcome: string;
  counterfactual_score: number;
  diverged: boolean;
  score_delta: number;
  causal_status: string;
  causal_explanation: string;
  is_multi_variable: boolean;
  diff_fields: { field: string; original: unknown; replay: unknown; changed: boolean }[];
}

export interface RiskAssessment {
  decision_id: string;
  decision_risk: number;
  evidence_completeness: number;
  provenance_completeness: number;
  control_coverage: number;
  policy_violation_count: number;
  replay_divergence: number | null;
  decision_sensitivity: number | null;
  risk_level: string;
  formulas: Record<string, string>;
}

export interface GovernanceFinding {
  control_id: string;
  control_name: string;
  status: string;
  reason: string;
  evidence: string[];
}

export interface ForensicExperiment {
  experiment_id: string;
  decision_id: string;
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
  replayability_status: string;
  replayability_reasons: string[];
  sensitivity: number;
  boundary: Record<string, unknown>;
  governance_impact: { control_id: string; control_name: string; before_status: string; after_status: string; changed: boolean }[];
}

export interface ForensicSweepOut {
  sweep_id: string;
  decision_id: string;
  baseline_outcome: string;
  baseline_score: number;
  timestamp: string;
  experiments: ForensicExperiment[];
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

export const liveApi = {
  listDecisions: () => req<DecisionSummary[]>("/decisions"),
  getDecision: (id: string) => req<DecisionDetail>(`/decisions/${id}`),
  getLineage: (id: string) => req<LineageGraph>(`/decisions/${id}/lineage`),
  replay: (id: string) => req<{ replay_id: string; outcome: string; score: number; replayability_status: string }>(`/decisions/${id}/replay`, { method: "POST" }),
  counterfactual: (id: string, mutations: { type: string; target: string; reason: string; payload?: Record<string, unknown> }[]) =>
    req<CounterfactualOut>(`/decisions/${id}/counterfactual`, { method: "POST", body: JSON.stringify({ mutations }) }),
  getRisk: (id: string) => req<RiskAssessment>(`/decisions/${id}/risk`),
  getGovernance: (id: string) => req<GovernanceFinding[]>(`/decisions/${id}/governance`),
  getEvents: (id: string) => req<{ event_id: string; timestamp: string; event_type: string; payload: Record<string, unknown> }[]>(`/decisions/${id}/events`),
  getIncident: (id: string) => req<any>(`/incidents/${id}`),
  getIncidentTimeline: (id: string) => req<any[]>(`/incidents/${id}/timeline`),
  getIncidentBlastRadius: (id: string) => req<any>(`/incidents/${id}/blast-radius`),
  policyImpactReplay: (policyId: string, body: any) =>
    req<any>(`/policies/${policyId}/impact-replay`, { method: "POST", body: JSON.stringify(body) }),
  forensicSweep: (id: string, approvedModel: string = "fraud-v3.2") =>
    req<ForensicSweepOut>(`/decisions/${id}/forensic-sweep`, { method: "POST", body: JSON.stringify({ approved_model: approvedModel }) }),
  health: () => req<{ status: string }>("/health"),
};
