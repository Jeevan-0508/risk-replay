import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { toRiskReplayHandoff, validateSwarmResearchCapture } from "../src/researchCapture.ts";

const candidate = {
  schema_version: "candidate-mo.v1",
  kind: "candidate_mo",
  data_class: "synthetic_simulation",
  exported_at: "2026-09-29T12:00:00.000Z",
  simulation: { seed: 42, sim_time_seconds_from_genesis: 4.5 },
  source: { repository: "Jeevan-0508/fraud-watch", repository_url: "https://github.com/Jeevan-0508/fraud-watch", revision: null, authenticity: "unverified_export" },
  taxonomy: { repository: "Jeevan-0508/freight-fraud-taxonomy", version: "1.0.0", source_commit: null, snapshot_sha256: null },
  candidate: {
    id: "fraud-watch:SIG-001", signature: "SIG-001", lifecycle_state: "DISCOVERED", source_state: "CANDIDATE",
    time_basis: "simulation_seconds_from_genesis", first_seen_at: 1, candidate_since: 2,
    review_started_at: null, resolved_at: null, resolution_note: null,
    supporting_cases: [{
      case_id: "MO-1", classification: "POTENTIAL_NEW_MO", classification_reason: null,
      recorded_at: 3, case_opened_at: 2, first_observed_at: 1, signal_types: ["route_deviation"],
      related_pattern_id: null, correlation_index: 4, correlation_index_semantics: "synthetic_signal_index_not_probability",
    }],
  },
};

function capture(candidateContext = null) {
  return {
    schema_version: "swarm-research-capture.v1",
    kind: "risk_swarm_research_capture",
    captured_at: "2026-09-29T12:00:00.000Z",
    source: { repository: "Jeevan-0508/risk-swarm", revision: null },
    research: {
      run_id: "RES-20260929120000", question: "A test query", question_origin: "operator_supplied",
      started_at: "2026-09-29T12:00:00.000Z", retrieval_status: "partial",
      attempts: [{ dimension: "background", provider: "news_rss", query: "test query", status: "unavailable", reason: "CORS blocked", returned: 0, retained: 0, ms: 3 }],
      source_records: [{
        evidence_id: "E-EXT-1", data_class: "external_source_content", role: "retrieved_source_record",
        provider: "news_rss", source_identity: "example.test", source_type: "news", query: "test query",
        url: "https://example.test/source", title: "Test-only source title", excerpt: "Synthetic test fixture; no factual claim.",
        content_hash: "fnv1a:12345678", content_hash_algorithm: "fnv1a", retrieved_at: "2026-09-29T12:00:00.000Z",
        stated_date: null, date_kind: "unknown", via_proxy: false, caveats: ["Test fixture only."], injection_suspected: false,
      }],
      dropped_sources: [], internal_search: { status: "not_run", hit_count: 0, content_exported: false },
    },
    hypothesis_context: candidateContext === null ? null : { data_class: "synthetic_simulation", role: "hypothesis_context_only", authenticity: "unverified_export", candidate: candidateContext },
    excluded_outputs: { model_conclusions: true, internal_knowledge_content: true, knowledge_promotion: true },
    integrity_note: "Fingerprints cover normalized excerpt text (or title); the algorithm may be non-cryptographic. They do not establish source authenticity, factual truth, source independence, or claim entailment.",
  };
}

test("accepts a research capture and reports its retrieved source separately", () => {
  const result = validateSwarmResearchCapture(capture());
  assert.equal(result.ok, true);
  if (result.ok) assert.equal(result.capture.research.source_records[0].data_class, "external_source_content");
});

test("accepts a synthetic candidate only under hypothesis_context", () => {
  const result = validateSwarmResearchCapture(capture(candidate));
  assert.equal(result.ok, true);
  if (result.ok) {
    assert.equal(result.capture.hypothesis_context.role, "hypothesis_context_only");
    assert.equal(result.capture.research.source_records.some((item) => item.data_class === "synthetic_simulation"), false);
  }
});

test("rejects synthetic records, duplicate ids, impossible attempt counts, and extra answer fields", () => {
  const synthetic = capture();
  synthetic.research.source_records[0].data_class = "synthetic_simulation";
  assert.equal(validateSwarmResearchCapture(synthetic).ok, false);

  const duplicate = capture();
  duplicate.research.source_records.push({ ...duplicate.research.source_records[0] });
  assert.equal(validateSwarmResearchCapture(duplicate).ok, false);

  const impossible = capture();
  impossible.research.attempts[0].retained = 1;
  assert.equal(validateSwarmResearchCapture(impossible).ok, false);

  const answer = capture();
  answer.research.answer = "A derived answer must not be in this packet.";
  assert.equal(validateSwarmResearchCapture(answer).ok, false);
});

test("Replay output stays unreviewed and explicitly says it was not rerun", () => {
  const parsed = validateSwarmResearchCapture(capture());
  assert.equal(parsed.ok, true);
  if (parsed.ok) {
    const handoff = toRiskReplayHandoff(parsed.capture, "2026-09-29T12:01:00.000Z");
    assert.equal(handoff.review_state, "unreviewed");
    assert.equal(handoff.replay_status, "not_replayed");
  }
});

test("the Replay wrapper contract pins the exact SWARM capture-schema revision", () => {
  const schema = JSON.parse(readFileSync(new URL("../../contracts/risk-replay-research-handoff.v1.schema.json", import.meta.url), "utf8"));
  assert.equal(schema.properties.review_state.const, "unreviewed");
  assert.equal(schema.properties.replay_status.const, "not_replayed");
  assert.match(schema.properties.capture.$ref, /risk-swarm\/24b068f3357753812df92e3e5a8a66ae36c08586\/contracts\/swarm-research-capture\.v1\.schema\.json$/);
});
