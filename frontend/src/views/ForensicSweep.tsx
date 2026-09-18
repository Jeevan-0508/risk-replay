import { useState } from "react";
import { api } from "../api";
import type { ForensicExperiment, ForensicSweepOut } from "../api";
import { OutcomeBadge, StatusBadge } from "../components/Badge";

interface Props {
  decisionId: string;
  originalOutcome: string;
  originalScore: number;
}

const CHECKLIST_STEPS = [
  "Load baseline decision context",
  "Generate single-variable mutations (evidence, tool results, controls)",
  "Run one counterfactual replay per mutation, isolated from the frozen baseline",
  "Classify each result (DECISION_CRITICAL / DECISION_IRRELEVANT / CONTRIBUTORY)",
  "Compute sensitivity ranking and governance impact",
];

export function ForensicSweep({ decisionId, originalOutcome, originalScore }: Props) {
  const [sweep, setSweep] = useState<ForensicSweepOut | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<ForensicExperiment | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    setSweep(null);
    setSelected(null);
    try {
      const r = await api.forensicSweep(decisionId);
      setSweep(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="panel">
      <div className="panel-header">Forensic Sweep &mdash; Automatic Counterfactual Testing</div>
      <div className="panel-body">
        <p style={{ fontSize: 12, color: "var(--text-2)", marginTop: 0 }}>
          Runs one deterministic single-variable counterfactual per evidence item, tool result and
          control already present in this decision's recorded context. Nothing here is fabricated:
          every number comes from the same engines behind Replay Lab.
        </p>

        <button className="btn primary" disabled={running} onClick={run}>
          {running ? "Running Forensic Sweep..." : "RUN FORENSIC SWEEP"}
        </button>

        {error && <div className="error-banner" style={{ marginTop: 12 }}>{error}</div>}

        {sweep && (
          <>
            {/* Honest recap: these are facts read off the real response, not a simulated progress bar. */}
            <ul style={{ marginTop: 16, marginBottom: 16, fontSize: 12, color: "var(--text-1)", paddingLeft: 18 }}>
              {CHECKLIST_STEPS.map((step, i) => (
                <li key={i} style={{ marginBottom: 4 }}>
                  <span style={{ color: "var(--ok)" }}>&#10003;</span> {step}
                  {i === 0 && ` -- ${sweep.baseline_outcome} @ ${sweep.baseline_score.toFixed(3)}`}
                  {i === 1 && ` -- ${sweep.summary.experiment_count} mutation(s) generated`}
                  {i === 2 && ` -- ${sweep.experiments.length} experiment(s) completed`}
                  {i === 3 && ` -- ${sweep.summary.decision_critical_count} critical, ${sweep.summary.decision_irrelevant_count} irrelevant, ${sweep.summary.contributory_count} contributory`}
                  {i === 4 && ` -- most sensitive: ${sweep.summary.most_sensitive_variable ?? "n/a"}, divergence ratio ${sweep.summary.divergence_ratio}`}
                </li>
              ))}
            </ul>

            <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 6 }}>Baseline</div>
                <div style={{ fontSize: 20 }}><OutcomeBadge outcome={originalOutcome} /></div>
                <div className="mono" style={{ fontSize: 12, color: "var(--text-1)", marginTop: 4 }}>score {originalScore.toFixed(3)}</div>
              </div>
            </div>

            <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginBottom: 8 }}>
              Experiments ({sweep.experiments.length}) &mdash; click a row for detail
            </div>
            <table className="diff-table">
              <thead>
                <tr><th>Variable</th><th>Mutation</th><th>Score Δ</th><th>Outcome</th><th>Diverged</th><th>Classification</th></tr>
              </thead>
              <tbody>
                {sweep.experiments.map((e) => (
                  <tr key={e.experiment_id} onClick={() => setSelected(e)} style={{ cursor: "pointer" }}>
                    <td>{e.variable} <span style={{ color: "var(--text-2)", fontSize: 11 }}>({e.variable_kind})</span></td>
                    <td>{e.mutation_type}</td>
                    <td className={e.diverged ? "changed" : ""}>{e.score_delta >= 0 ? "+" : ""}{e.score_delta.toFixed(3)}</td>
                    <td><OutcomeBadge outcome={e.counterfactual_outcome} /></td>
                    <td>{e.diverged ? "YES" : "no"}</td>
                    <td><StatusBadge status={e.causal_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>

            <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", margin: "16px 0 8px" }}>
              Sensitivity Ranking (min(1, |Δscore| / block_threshold))
            </div>
            {[...sweep.experiments].sort((a, b) => b.sensitivity - a.sensitivity).map((e) => (
              <div key={e.experiment_id} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                <div style={{ width: 60, fontSize: 12 }} className="mono">{e.variable}</div>
                <div style={{ flex: 1, background: "var(--bg-2)", height: 14, borderRadius: 3, overflow: "hidden" }}>
                  <div style={{ width: `${e.sensitivity * 100}%`, height: "100%", background: e.diverged ? "var(--accent)" : "var(--text-2)" }} />
                </div>
                <div style={{ width: 50, fontSize: 12, textAlign: "right" }} className="mono">{e.sensitivity.toFixed(3)}</div>
              </div>
            ))}

            {sweep.unsupported_mutation_types.length > 0 && (
              <details style={{ marginTop: 16, fontSize: 12, color: "var(--text-2)" }}>
                <summary style={{ cursor: "pointer" }}>
                  Mutation types NOT auto-generated ({sweep.unsupported_mutation_types.length}) -- why
                </summary>
                <ul style={{ paddingLeft: 18 }}>
                  {sweep.unsupported_mutation_types.map((u) => (
                    <li key={u.mutation_type}><strong>{u.mutation_type}</strong>: {u.reason}</li>
                  ))}
                </ul>
              </details>
            )}

            {selected && (
              <div className="panel" style={{ marginTop: 16, borderColor: "var(--accent)" }}>
                <div className="panel-header">Experiment {selected.experiment_id} &mdash; {selected.variable}</div>
                <div className="panel-body">
                  <div className={`causal-banner ${selected.diverged ? "" : "irrelevant"}`}>
                    <span className="causal-status-tag">{selected.causal_status}</span>
                    {selected.causal_explanation}
                  </div>

                  <div style={{ display: "flex", gap: 16, margin: "12px 0" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase" }}>Baseline</div>
                      <OutcomeBadge outcome={selected.baseline_outcome} /> <span className="mono">{selected.baseline_score.toFixed(3)}</span>
                    </div>
                    <div style={{ alignSelf: "center", color: "var(--text-2)" }}>&rarr;</div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase" }}>Counterfactual</div>
                      <OutcomeBadge outcome={selected.counterfactual_outcome} /> <span className="mono">{selected.counterfactual_score.toFixed(3)}</span>
                    </div>
                  </div>

                  <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginTop: 8 }}>Decision Boundary</div>
                  <table className="diff-table">
                    <tbody>
                      {Object.entries(selected.boundary).map(([k, v]) => (
                        <tr key={k}><td>{k}</td><td colSpan={2}>{String(v)}</td></tr>
                      ))}
                    </tbody>
                  </table>

                  {selected.governance_impact.length > 0 && (
                    <>
                      <div style={{ fontSize: 11, color: "var(--text-2)", textTransform: "uppercase", marginTop: 12 }}>Governance Impact</div>
                      <table className="diff-table">
                        <thead><tr><th>Control</th><th>Before</th><th>After</th></tr></thead>
                        <tbody>
                          {selected.governance_impact.map((g) => (
                            <tr key={g.control_id}>
                              <td>{g.control_name} ({g.control_id})</td>
                              <td className={g.changed ? "changed" : ""}>{g.before_status}</td>
                              <td className={g.changed ? "changed" : ""}>{g.after_status}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </>
                  )}

                  <div style={{ marginTop: 12, fontSize: 11, color: "var(--warn)", border: "1px solid var(--warn)", borderRadius: 4, padding: 8 }}>
                    Methodological limitation: this finding is scoped to the replay model above. It does
                    not establish real-world causation, only that this decision, under this exact
                    deterministic scoring rule, would have produced a different outcome had this one
                    variable been absent.
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
