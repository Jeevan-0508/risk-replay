export type InvestigationHandoff = {
  schema_version: "risk-replay-investigation-handoff.v1";
  kind: "risk_replay_investigation_handoff";
  created_at: string;
  review_state: "unreviewed";
  replay_status: "frozen_context_reconstructed";
  snapshot: { schema_version: "swarm-investigation-snapshot.v1"; kind: "risk_swarm_investigation_snapshot"; captured_at: string; capture: any; analysis: any; outcome: { status: "not_observed"; correctness: "unknown"; record: null }; unknowns: string[]; knowledge_promotion: "prohibited" };
  reconstruction: any;
};

const object = (v: unknown): v is Record<string, any> => v !== null && typeof v === "object" && !Array.isArray(v);
const exact = (v: unknown, keys: string[]) => object(v) && Object.keys(v).length === keys.length && keys.every((k) => Object.hasOwn(v, k));
const iso = (v: unknown): v is string => typeof v === "string" && v.length < 100 && Number.isFinite(Date.parse(v));
const list = (v: unknown): v is string[] => Array.isArray(v) && v.length <= 500 && v.every((x) => typeof x === "string" && x.length <= 300) && new Set(v).size === v.length;

export function validateInvestigationHandoff(value: unknown): { ok: true; handoff: InvestigationHandoff } | { ok: false; error: string } {
  try {
    if (JSON.stringify(value).length > 2_000_000 || !exact(value, ["schema_version", "kind", "created_at", "review_state", "replay_status", "snapshot", "reconstruction"])) return { ok: false, error: "Expected the strict frozen investigation envelope." };
    const v = value as any; const s = v.snapshot; const c = s?.capture; const r = c?.research;
    if (v.schema_version !== "risk-replay-investigation-handoff.v1" || v.kind !== "risk_replay_investigation_handoff" || !iso(v.created_at) || v.review_state !== "unreviewed" || v.replay_status !== "frozen_context_reconstructed") return { ok: false, error: "Unsupported investigation handoff state." };
    if (!exact(s, ["schema_version", "kind", "captured_at", "capture", "analysis", "outcome", "unknowns", "knowledge_promotion"]) || s.schema_version !== "swarm-investigation-snapshot.v1" || s.kind !== "risk_swarm_investigation_snapshot" || !iso(s.captured_at) || Date.parse(v.created_at) < Date.parse(s.captured_at) || !list(s.unknowns) || s.knowledge_promotion !== "prohibited") return { ok: false, error: "Frozen snapshot is malformed." };
    if (!exact(c, ["schema_version", "kind", "captured_at", "source", "research", "hypothesis_context", "excluded_outputs", "integrity_note"]) || c.schema_version !== "swarm-research-capture.v1" || c.kind !== "risk_swarm_research_capture" || !iso(c.captured_at) || c.source?.repository !== "Jeevan-0508/risk-swarm" || !(c.source.revision === null || /^[a-f0-9]{40}$/.test(c.source.revision))) return { ok: false, error: "SWARM source provenance is malformed." };
    if (!exact(r, ["run_id", "question", "question_origin", "started_at", "retrieval_status", "attempts", "source_records", "dropped_sources", "internal_search"]) || typeof r.run_id !== "string" || typeof r.question !== "string" || r.question_origin !== "operator_supplied" || !iso(r.started_at) || !Array.isArray(r.source_records)) return { ok: false, error: "Research capture is malformed." };
    const ids = new Set<string>();
    for (const source of r.source_records) {
      if (!object(source) || source.data_class !== "external_source_content" || source.role !== "retrieved_source_record" || typeof source.evidence_id !== "string" || ids.has(source.evidence_id) || !iso(source.retrieved_at) || !["sha256", "fnv1a"].includes(source.content_hash_algorithm)) return { ok: false, error: "Synthetic, malformed or duplicate source record." };
      try { if (!["http:", "https:"].includes(new URL(source.url).protocol)) return { ok: false, error: "Source URL must be HTTP(S)." }; } catch { return { ok: false, error: "Source URL is invalid." }; }
      ids.add(source.evidence_id);
    }
    if (!exact(s.analysis, ["status", "selected_source_ids", "omitted_source_ids", "positions", "disagreement", "decision", "trace"]) || !["recorded", "not_run"].includes(s.analysis.status) || !list(s.analysis.selected_source_ids) || !list(s.analysis.omitted_source_ids) || s.analysis.selected_source_ids.some((id: string) => !ids.has(id)) || s.analysis.omitted_source_ids.some((id: string) => ids.has(id))) return { ok: false, error: "Analysis references are invalid." };
    if (!exact(s.outcome, ["status", "correctness", "record"]) || s.outcome.status !== "not_observed" || s.outcome.correctness !== "unknown" || s.outcome.record !== null) return { ok: false, error: "Outcome correctness must remain unknown." };
    if (c.hypothesis_context !== null && (!object(c.hypothesis_context) || c.hypothesis_context.data_class !== "synthetic_simulation" || c.hypothesis_context.role !== "hypothesis_context_only")) return { ok: false, error: "Synthetic candidate context cannot be relabelled as evidence." };
    return { ok: true, handoff: v as InvestigationHandoff };
  } catch { return { ok: false, error: "Could not parse investigation handoff safely." }; }
}

export function reconstructFrozenContext(handoff: InvestigationHandoff) {
  return { question: handoff.snapshot.capture.research.question, source_record_ids: handoff.snapshot.capture.research.source_records.map((s: any) => s.evidence_id), selected_source_ids: [...handoff.snapshot.analysis.selected_source_ids], analysis_status: handoff.snapshot.analysis.status, outcome: handoff.snapshot.outcome, live_provider_calls: 0, knowledge_promotion: false, synthetic_context_used_as_evidence: false };
}
