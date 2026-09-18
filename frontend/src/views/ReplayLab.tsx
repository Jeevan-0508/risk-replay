import { useState } from "react";
import { api } from "../api";
import type { CounterfactualOut, EvidenceOut } from "../api";
import { OutcomeBadge } from "../components/Badge";

interface Props {
  decisionId: string;
  evidence: EvidenceOut[];
  originalOutcome: string;
  originalScore: number;
}

type MutationDraft = { type: string; target: string; reason: string; payload?: Record<string, unknown> };

export function ReplayLab({ decisionId, evidence, originalOutcome, originalScore }: Props) {
  const [mutations, setMutations] = useState<MutationDraft[]>([]);
  const [result, setResult] = useState<CounterfactualOut | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function addMutation() {
    setMutations((m) => [...m, { type: "REMOVE_EVIDENCE", target: evidence[0]?.evidence_id ?? "", reason: "investigator hypothesis" }]);
  }

  function updateMutation(i: number, patch: Partial<MutationDraft>) {
    setMutations((m) => m.map((mut, idx) => (idx === i ? { ...mut, ...patch } : mut)));
  }

  function removeMutation(i: number) {
    setMutations((m) => m.filter((_, idx) => idx !== i));
  }

  async function runCounterfactual() {
    if (mutations.length === 0) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.counterfactual(decisionId, mutations);
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">Replay Lab &mdash; Mutation Lab (Counterfactual Engine)</div>
      <div className="panel-body">
        <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 6 }}>Original</div>
            <div style={{ fontSize: 20 }}><OutcomeBadge outcome={originalOutcome} /></div>
            <div className="mono" style={{ fontSize: 12, color: "var(--text-1)", marginTop: 4 }}>score {originalScore.toFixed(3)}</div>
          </div>
          {result && (
            <>
              <div style={{ alignSelf: "center", fontSize: 22, color: "var(--text-2)" }}>&rarr;</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 6 }}>Counterfactual</div>
                <div style={{ fontSize: 20 }}><OutcomeBadge outcome={result.counterfactual_outcome} /></div>
                <div className="mono" style={{ fontSize: 12, color: "var(--text-1)", marginTop: 4 }}>
                  score {result.counterfactual_score.toFixed(3)} ({result.score_delta >= 0 ? "+" : ""}{result.score_delta.toFixed(3)})
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 6 }}>Divergence</div>
                <div style={{ fontSize: 20, color: result.diverged ? "var(--accent)" : "var(--ok)", fontWeight: 700 }}>
                  {result.diverged ? "YES" : "NO"}
                </div>
              </div>
            </>
          )}
        </div>

        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 8 }}>
            Mutations ({mutations.length}) {mutations.length > 1 && <span style={{ color: "var(--warn)" }}>-- multi-variable, causal isolation will be limited</span>}
          </div>
          {mutations.map((m, i) => (
            <div className="mutation-row" key={i}>
              <select value={m.type} onChange={(e) => updateMutation(i, { type: e.target.value })}>
                <option value="REMOVE_EVIDENCE">Remove Evidence</option>
                <option value="CHANGE_THRESHOLD">Change Threshold</option>
              </select>
              {m.type === "REMOVE_EVIDENCE" && (
                <select value={m.target} onChange={(e) => updateMutation(i, { target: e.target.value })}>
                  {evidence.map((e) => (
                    <option key={e.evidence_id} value={e.evidence_id}>{e.evidence_id} ({e.kind})</option>
                  ))}
                </select>
              )}
              {m.type === "CHANGE_THRESHOLD" && (
                <>
                  <select value={(m.payload?.field as string) || "block_threshold"} onChange={(e) => updateMutation(i, { payload: { ...m.payload, field: e.target.value } })}>
                    <option value="block_threshold">block_threshold</option>
                    <option value="review_threshold">review_threshold</option>
                  </select>
                  <input type="number" step="0.01" min="0" max="1" placeholder="new value"
                    value={(m.payload?.value as number) ?? ""}
                    onChange={(e) => updateMutation(i, { payload: { ...m.payload, value: parseFloat(e.target.value), field: (m.payload?.field as string) || "block_threshold" }, target: "policy" })} />
                </>
              )}
              <input type="text" placeholder="reason" value={m.reason} onChange={(e) => updateMutation(i, { reason: e.target.value })} style={{ flex: 1 }} />
              <button className="btn small" onClick={() => removeMutation(i)}>remove</button>
            </div>
          ))}
          <button className="btn" onClick={addMutation} style={{ marginTop: 8 }}>+ Add Mutation</button>
        </div>

        <button className="btn primary" disabled={mutations.length === 0 || running} onClick={runCounterfactual}>
          {running ? "Running..." : "Run Counterfactual"}
        </button>

        {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}

        {result && (
          <div style={{ marginTop: 16 }}>
            <div className={`causal-banner ${result.diverged ? "" : "irrelevant"}`}>
              <span className="causal-status-tag">{result.causal_status}</span>
              {result.causal_explanation}
            </div>

            <table className="diff-table">
              <thead><tr><th>Field</th><th>Original</th><th>Replay</th></tr></thead>
              <tbody>
                {result.diff_fields.map((f) => (
                  <tr key={f.field}>
                    <td>{f.field}</td>
                    <td className={f.changed ? "changed" : ""}>{String(f.original)}</td>
                    <td className={f.changed ? "changed" : ""}>{String(f.replay)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
