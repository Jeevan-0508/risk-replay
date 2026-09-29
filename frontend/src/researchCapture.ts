export interface SwarmSourceRecord {
  evidence_id: string;
  data_class: "external_source_content";
  role: "retrieved_source_record";
  provider: string;
  source_identity: string;
  source_type: string;
  query: string;
  url: string;
  title: string;
  excerpt: string;
  content_hash: string;
  content_hash_algorithm: "sha256" | "fnv1a";
  retrieved_at: string;
  stated_date: string | null;
  date_kind: string;
  via_proxy: boolean;
  caveats: string[];
  injection_suspected: boolean;
}

export interface SwarmResearchCapture {
  schema_version: "swarm-research-capture.v1";
  kind: "risk_swarm_research_capture";
  captured_at: string;
  source: { repository: "Jeevan-0508/risk-swarm"; revision: string | null };
  research: {
    run_id: string;
    question: string;
    question_origin: "operator_supplied";
    started_at: string;
    retrieval_status: "ok" | "partial" | "search_failed" | "limit_reached";
    attempts: Array<{ dimension: string; provider: string; query: string; status: string; reason: string | null; returned: number; retained: number; ms: number }>;
    source_records: SwarmSourceRecord[];
    dropped_sources: Array<{ reason: string; title: string; detail: string }>;
    internal_search: { status: string; hit_count: number; content_exported: false };
  };
  hypothesis_context: null | {
    data_class: "synthetic_simulation";
    role: "hypothesis_context_only";
    authenticity: "unverified_export";
    candidate: Record<string, unknown>;
  };
  excluded_outputs: { model_conclusions: true; internal_knowledge_content: true; knowledge_promotion: true };
  integrity_note: string;
}

export interface RiskReplayHandoff {
  schema_version: "risk-replay-research-handoff.v1";
  kind: "risk_replay_research_handoff";
  created_at: string;
  review_state: "unreviewed";
  replay_status: "not_replayed";
  capture: SwarmResearchCapture;
}

type Validation = { ok: true; capture: SwarmResearchCapture } | { ok: false; error: string };

const providers = new Set(["wikipedia", "wikidata", "openalex", "crossref", "hackernews", "worldbank", "duckduckgo", "news_rss"]);
const attemptStatuses = new Set(["ok", "empty", "search_failed", "unavailable", "skipped_budget"]);
const sourceTypes = new Set(["regulator", "industry_body", "news", "portfolio_kb", "academic", "statistical_body", "reference_work"]);
const dateKinds = new Set(["published", "revised", "indexed", "observed", "unknown"]);
const retrievalStatuses = new Set(["ok", "partial", "search_failed", "limit_reached"]);
const internalStatuses = new Set(["not_run", "ok", "empty", "unavailable"]);

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, expected: string[]): boolean {
  const actual = Object.keys(value).sort();
  return actual.length === expected.length && actual.every((key, i) => key === [...expected].sort()[i]);
}

function text(value: unknown): value is string { return typeof value === "string"; }
function isoDate(value: unknown): value is string { return text(value) && !Number.isNaN(Date.parse(value)) && value.includes("T"); }
function nonnegative(value: unknown): value is number { return typeof value === "number" && Number.isFinite(value) && value >= 0; }

function candidateWrapperValid(value: unknown): value is Record<string, unknown> {
  if (!record(value) || !exactKeys(value, ["data_class", "role", "authenticity", "candidate"])) return false;
  if (value.data_class !== "synthetic_simulation" || value.role !== "hypothesis_context_only" || value.authenticity !== "unverified_export") return false;
  const candidate = value.candidate;
  if (!record(candidate) || !exactKeys(candidate, ["schema_version", "kind", "data_class", "exported_at", "simulation", "source", "taxonomy", "candidate"])) return false;
  if (candidate.schema_version !== "candidate-mo.v1" || candidate.kind !== "candidate_mo" || candidate.data_class !== "synthetic_simulation" || !isoDate(candidate.exported_at)) return false;
  if (!record(candidate.simulation) || !exactKeys(candidate.simulation, ["seed", "sim_time_seconds_from_genesis"]) || !Number.isInteger(candidate.simulation.seed) || !nonnegative(candidate.simulation.sim_time_seconds_from_genesis)) return false;
  if (!record(candidate.source) || !exactKeys(candidate.source, ["repository", "repository_url", "revision", "authenticity"]) || candidate.source.repository !== "Jeevan-0508/fraud-watch" || candidate.source.repository_url !== "https://github.com/Jeevan-0508/fraud-watch" || candidate.source.authenticity !== "unverified_export") return false;
  if (!(candidate.source.revision === null || (text(candidate.source.revision) && /^[0-9a-f]{40}$/.test(candidate.source.revision)))) return false;
  if (!record(candidate.taxonomy) || !exactKeys(candidate.taxonomy, ["repository", "version", "source_commit", "snapshot_sha256"]) || candidate.taxonomy.repository !== "Jeevan-0508/freight-fraud-taxonomy" || !text(candidate.taxonomy.version) || !candidate.taxonomy.version) return false;
  if (!(candidate.taxonomy.source_commit === null || (text(candidate.taxonomy.source_commit) && /^[0-9a-f]{40}$/.test(candidate.taxonomy.source_commit)))) return false;
  if (!(candidate.taxonomy.snapshot_sha256 === null || (text(candidate.taxonomy.snapshot_sha256) && /^[0-9a-f]{64}$/.test(candidate.taxonomy.snapshot_sha256)))) return false;

  const c = candidate.candidate;
  const lifecycle = new Map([["DISCOVERED", "CANDIDATE"], ["UNDER_REVIEW", "REVIEW"], ["VALIDATED", "VALIDATED"], ["REJECTED", "REJECTED"]]);
  if (!record(c) || !exactKeys(c, ["id", "signature", "lifecycle_state", "source_state", "time_basis", "first_seen_at", "candidate_since", "review_started_at", "resolved_at", "resolution_note", "supporting_cases"])) return false;
  if (!text(c.signature) || !c.signature || c.id !== `fraud-watch:${c.signature}` || lifecycle.get(String(c.lifecycle_state)) !== c.source_state || c.time_basis !== "simulation_seconds_from_genesis") return false;
  if (!nonnegative(c.first_seen_at) || !nonnegative(c.candidate_since) || c.first_seen_at > c.candidate_since || c.candidate_since > candidate.simulation.sim_time_seconds_from_genesis) return false;
  if (!(c.review_started_at === null || nonnegative(c.review_started_at)) || !(c.resolved_at === null || nonnegative(c.resolved_at)) || !(c.resolution_note === null || (text(c.resolution_note) && c.resolution_note.length <= 2000))) return false;
  if (c.lifecycle_state === "DISCOVERED" && (c.review_started_at !== null || c.resolved_at !== null)) return false;
  if (c.lifecycle_state === "UNDER_REVIEW" && (c.review_started_at === null || c.resolved_at !== null)) return false;
  if (["VALIDATED", "REJECTED"].includes(String(c.lifecycle_state)) && (c.review_started_at === null || c.resolved_at === null)) return false;
  if (c.review_started_at !== null && (c.review_started_at < c.candidate_since || c.review_started_at > candidate.simulation.sim_time_seconds_from_genesis)) return false;
  if (c.resolved_at !== null && (c.review_started_at === null || c.resolved_at < c.review_started_at || c.resolved_at > candidate.simulation.sim_time_seconds_from_genesis)) return false;
  if (!Array.isArray(c.supporting_cases) || c.supporting_cases.length === 0) return false;
  const caseIds = new Set<string>();
  for (const support of c.supporting_cases) {
    const required = ["case_id", "classification", "classification_reason", "recorded_at", "case_opened_at", "first_observed_at", "signal_types", "related_pattern_id", "correlation_index", "correlation_index_semantics"];
    if (!record(support) || !(exactKeys(support, required) || exactKeys(support, [...required, "current_classification"]))) return false;
    if (!text(support.case_id) || !/^MO-[0-9]+$/.test(support.case_id) || caseIds.has(support.case_id)) return false;
    caseIds.add(support.case_id);
    const classifications = ["KNOWN_MO", "MO_VARIANT", "POTENTIAL_NEW_MO", "EMERGING_BEHAVIOR"];
    if (!text(support.classification) || !classifications.includes(support.classification)) return false;
    if ("current_classification" in support && (!text(support.current_classification) || !classifications.includes(support.current_classification))) return false;
    if (!(support.classification_reason === null || (text(support.classification_reason) && support.classification_reason.length <= 500))) return false;
    const firstObserved = support.first_observed_at;
    const caseOpened = support.case_opened_at;
    const recorded = support.recorded_at;
    if (!nonnegative(firstObserved) || !nonnegative(caseOpened) || !nonnegative(recorded)) return false;
    if (firstObserved > caseOpened || caseOpened > recorded || recorded < c.candidate_since || recorded > candidate.simulation.sim_time_seconds_from_genesis) return false;
    if (!Array.isArray(support.signal_types) || support.signal_types.length === 0 || !support.signal_types.every((entry) => text(entry) && entry.length > 0) || new Set(support.signal_types).size !== support.signal_types.length) return false;
    if (!(support.related_pattern_id === null || (text(support.related_pattern_id) && /^FFT-[0-9]{3}$/.test(support.related_pattern_id)))) return false;
    if (!Number.isInteger(support.correlation_index) || !nonnegative(support.correlation_index) || support.correlation_index > 100 || support.correlation_index_semantics !== "synthetic_signal_index_not_probability") return false;
  }
  return true;
}

export function validateSwarmResearchCapture(value: unknown): Validation {
  if (!record(value) || !exactKeys(value, ["schema_version", "kind", "captured_at", "source", "research", "hypothesis_context", "excluded_outputs", "integrity_note"])) {
    return { ok: false, error: "File does not match the strict SWARM research-capture v1 envelope." };
  }
  if (value.schema_version !== "swarm-research-capture.v1" || value.kind !== "risk_swarm_research_capture" || !isoDate(value.captured_at)) {
    return { ok: false, error: "Unsupported or malformed SWARM research-capture version." };
  }
  if (!record(value.source) || !exactKeys(value.source, ["repository", "revision"]) || value.source.repository !== "Jeevan-0508/risk-swarm") {
    return { ok: false, error: "Source provenance is malformed." };
  }
  if (value.source.revision !== null && (!text(value.source.revision) || !/^[0-9a-f]{40}$/.test(value.source.revision))) return { ok: false, error: "Source revision is not a full commit hash or null." };
  if (!record(value.research)) return { ok: false, error: "Research capture is missing." };
  const research = value.research;
  if (!exactKeys(research, ["run_id", "question", "question_origin", "started_at", "retrieval_status", "attempts", "source_records", "dropped_sources", "internal_search"])) return { ok: false, error: "Research capture contains missing or unexpected fields." };
  if (!text(research.run_id) || !text(research.question) || research.question_origin !== "operator_supplied" || !isoDate(research.started_at) || !text(research.retrieval_status) || !retrievalStatuses.has(research.retrieval_status)) return { ok: false, error: "Research run metadata is malformed." };
  if (!Array.isArray(research.attempts) || !Array.isArray(research.source_records) || !Array.isArray(research.dropped_sources)) return { ok: false, error: "Research record lists are malformed." };
  for (const attempt of research.attempts) {
    if (!record(attempt) || !exactKeys(attempt, ["dimension", "provider", "query", "status", "reason", "returned", "retained", "ms"])) return { ok: false, error: "A retrieval attempt has missing or unexpected fields." };
    if (!text(attempt.dimension) || !text(attempt.provider) || !providers.has(attempt.provider) || !text(attempt.query) || !text(attempt.status) || !attemptStatuses.has(attempt.status)) return { ok: false, error: "A retrieval attempt has invalid provider or status." };
    if (!(attempt.reason === null || text(attempt.reason)) || !Number.isInteger(attempt.returned) || !Number.isInteger(attempt.retained) || !nonnegative(attempt.returned) || !nonnegative(attempt.retained) || attempt.retained > attempt.returned || !nonnegative(attempt.ms)) return { ok: false, error: "A retrieval attempt has invalid counts or duration." };
  }
  const ids = new Set<string>();
  for (const source of research.source_records) {
    if (!record(source) || !exactKeys(source, ["evidence_id", "data_class", "role", "provider", "source_identity", "source_type", "query", "url", "title", "excerpt", "content_hash", "content_hash_algorithm", "retrieved_at", "stated_date", "date_kind", "via_proxy", "caveats", "injection_suspected"])) return { ok: false, error: "A source record has missing or unexpected fields." };
    if (source.data_class !== "external_source_content" || source.role !== "retrieved_source_record") return { ok: false, error: "A source record must be external source content; synthetic data is not accepted in this list." };
    if (!text(source.evidence_id) || ids.has(source.evidence_id)) return { ok: false, error: "Source-record identifiers must be present and unique." };
    ids.add(source.evidence_id);
    if (!text(source.provider) || !providers.has(source.provider) || !text(source.source_type) || !sourceTypes.has(source.source_type)) return { ok: false, error: "A source record has an unknown provider or source type." };
    if (![source.source_identity, source.query, source.title, source.excerpt, source.content_hash].every(text) || !text(source.content_hash_algorithm) || !["sha256", "fnv1a"].includes(source.content_hash_algorithm)) return { ok: false, error: "A source record has malformed content or fingerprint metadata." };
    try { const url = new URL(String(source.url)); if (url.protocol !== "https:" && url.protocol !== "http:") throw new Error(); } catch { return { ok: false, error: "A source record must have an HTTP(S) source URL." }; }
    if (!isoDate(source.retrieved_at) || !(source.stated_date === null || text(source.stated_date)) || !text(source.date_kind) || !dateKinds.has(source.date_kind)) return { ok: false, error: "A source record has malformed date provenance." };
    if (typeof source.via_proxy !== "boolean" || typeof source.injection_suspected !== "boolean" || !Array.isArray(source.caveats) || !source.caveats.every(text)) return { ok: false, error: "A source record has malformed caveat metadata." };
  }
  if (!research.source_records.every((item) => record(item) && item.data_class === "external_source_content")) return { ok: false, error: "Synthetic candidates cannot be source records." };
  if (!research.dropped_sources.every((item) => record(item) && ["no_location", "empty_text"].includes(String(item.reason)) && text(item.title) && text(item.detail) && exactKeys(item, ["reason", "title", "detail"]))) return { ok: false, error: "Dropped-source report is malformed." };
  if (!record(research.internal_search) || !exactKeys(research.internal_search, ["status", "hit_count", "content_exported"]) || !text(research.internal_search.status) || !internalStatuses.has(research.internal_search.status) || !Number.isInteger(research.internal_search.hit_count) || !nonnegative(research.internal_search.hit_count) || research.internal_search.content_exported !== false) return { ok: false, error: "Internal-search disclosure is malformed." };
  if (!(value.hypothesis_context === null || candidateWrapperValid(value.hypothesis_context))) return { ok: false, error: "Candidate context must remain a validated synthetic hypothesis object." };
  if (!record(value.excluded_outputs) || !exactKeys(value.excluded_outputs, ["model_conclusions", "internal_knowledge_content", "knowledge_promotion"]) || value.excluded_outputs.model_conclusions !== true || value.excluded_outputs.internal_knowledge_content !== true || value.excluded_outputs.knowledge_promotion !== true) return { ok: false, error: "Capture must explicitly exclude conclusions, internal text and knowledge promotion." };
  if (value.integrity_note !== "Fingerprints cover normalized excerpt text (or title); the algorithm may be non-cryptographic. They do not establish source authenticity, factual truth, source independence, or claim entailment.") return { ok: false, error: "Capture integrity limitation is missing." };
  return { ok: true, capture: value as unknown as SwarmResearchCapture };
}

export function toRiskReplayHandoff(capture: SwarmResearchCapture, createdAt: string): RiskReplayHandoff {
  return {
    schema_version: "risk-replay-research-handoff.v1",
    kind: "risk_replay_research_handoff",
    created_at: createdAt,
    review_state: "unreviewed",
    replay_status: "not_replayed",
    capture,
  };
}
