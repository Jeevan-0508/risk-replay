import { useEffect, useState } from "react";
import { api } from "../api";
import type { DecisionSummary } from "../api";

export function CommandCenter({ onOpenDecision }: { onOpenDecision: (id: string) => void }) {
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDecisions().then(setDecisions).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error-banner">Could not reach the RISK//REPLAY API: {error}. Is the backend running on :8000?</div>;
  if (!decisions) return <div className="loading">Loading command center...</div>;

  const blocked = decisions.filter((d) => d.final_outcome === "BLOCK").length;
  const review = decisions.filter((d) => d.final_outcome === "REVIEW").length;
  const allowed = decisions.filter((d) => d.final_outcome === "ALLOW").length;
  const highRisk = decisions.filter((d) => d.risk_score >= 0.6).length;
  const avgConfidence = decisions.reduce((s, d) => s + d.confidence, 0) / decisions.length;

  return (
    <div>
      <div className="page-header">
        <h1>Command Center</h1>
        <div className="sub">Overview of all ingested decisions across systems, models and policies.</div>
      </div>

      <div className="grid-metrics">
        <div className="metric-card"><div className="label">Total Decisions</div><div className="value">{decisions.length}</div></div>
        <div className="metric-card"><div className="label">Blocked</div><div className="value accent">{blocked}</div></div>
        <div className="metric-card"><div className="label">Review</div><div className="value warn">{review}</div></div>
        <div className="metric-card"><div className="label">Allowed</div><div className="value ok">{allowed}</div></div>
        <div className="metric-card"><div className="label">High Risk (&gt;=0.6)</div><div className="value accent">{highRisk}</div></div>
        <div className="metric-card"><div className="label">Avg Confidence</div><div className="value">{avgConfidence.toFixed(3)}</div></div>
      </div>

      <div className="panel">
        <div className="panel-header">Recent Decisions</div>
        <div className="panel-body" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Decision ID</th><th>System</th><th>Model</th><th>Policy</th><th>Outcome</th><th>Score</th></tr>
            </thead>
            <tbody>
              {decisions.slice(0, 12).map((d) => (
                <tr key={d.decision_id} onClick={() => onOpenDecision(d.decision_id)}>
                  <td className="mono">{d.decision_id}</td>
                  <td>{d.system}</td>
                  <td className="mono">{d.model_id}</td>
                  <td className="mono">{d.policy_id}</td>
                  <td>{d.final_outcome}</td>
                  <td className="mono">{d.risk_score.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="footer-note">
        Every number above is computed live from `/decisions` -- there is no cached or hardcoded summary.
      </div>
    </div>
  );
}
