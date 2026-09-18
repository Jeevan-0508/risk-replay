import { useEffect, useState } from "react";
import { api } from "../api";
import type { DecisionSummary } from "../api";
import { OutcomeBadge } from "../components/Badge";

export function DecisionVault({ onOpenDecision }: { onOpenDecision: (id: string) => void }) {
  const [decisions, setDecisions] = useState<DecisionSummary[] | null>(null);
  const [filter, setFilter] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState("ALL");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listDecisions().then(setDecisions).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="error-banner">{error}</div>;
  if (!decisions) return <div className="loading">Loading decision vault...</div>;

  const filtered = decisions.filter((d) => {
    if (outcomeFilter !== "ALL" && d.final_outcome !== outcomeFilter) return false;
    if (filter && !d.decision_id.toLowerCase().includes(filter.toLowerCase()) && !d.system.toLowerCase().includes(filter.toLowerCase())) return false;
    return true;
  });

  return (
    <div>
      <div className="page-header">
        <h1>Decision Vault</h1>
        <div className="sub">Search and filter every historical decision. Click a row to open its forensic record.</div>
      </div>

      <div style={{ display: "flex", gap: 10, marginBottom: 14 }}>
        <input type="text" placeholder="Search decision id or system..." value={filter} onChange={(e) => setFilter(e.target.value)} style={{ width: 260 }} />
        <select value={outcomeFilter} onChange={(e) => setOutcomeFilter(e.target.value)}>
          <option value="ALL">All outcomes</option>
          <option value="BLOCK">BLOCK</option>
          <option value="REVIEW">REVIEW</option>
          <option value="ALLOW">ALLOW</option>
        </select>
        <div style={{ color: "var(--text-2)", alignSelf: "center", fontSize: 11 }}>{filtered.length} of {decisions.length}</div>
      </div>

      <div className="panel">
        <div className="panel-body" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Decision ID</th><th>Time</th><th>System</th><th>Model</th><th>Policy</th><th>Outcome</th><th>Risk</th><th>Evidence</th></tr>
            </thead>
            <tbody>
              {filtered.map((d) => (
                <tr key={d.decision_id} onClick={() => onOpenDecision(d.decision_id)}>
                  <td className="mono">{d.decision_id}</td>
                  <td className="mono">{new Date(d.timestamp).toISOString().slice(0, 16).replace("T", " ")}</td>
                  <td>{d.system}</td>
                  <td className="mono">{d.model_id}</td>
                  <td className="mono">{d.policy_id}</td>
                  <td><OutcomeBadge outcome={d.final_outcome} /></td>
                  <td className="mono">{d.risk_score.toFixed(3)}</td>
                  <td className="mono">{d.evidence_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
