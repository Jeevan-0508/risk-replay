import { useEffect, useState } from "react";
import { api } from "../api";
import type { DecisionDetail, LineageGraph, RiskAssessment, GovernanceFinding, BoundaryProfile, DecisionDNA } from "../api";
import { OutcomeBadge, StatusBadge } from "../components/Badge";
import { ReplayLab } from "./ReplayLab";
import { ForensicSweep } from "./ForensicSweep";

export function DecisionForensics({ decisionId }: { decisionId: string }) {
  const [decision, setDecision] = useState<DecisionDetail | null>(null);
  const [lineage, setLineage] = useState<LineageGraph | null>(null);
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [governance, setGovernance] = useState<GovernanceFinding[] | null>(null);
  const [boundary, setBoundary] = useState<BoundaryProfile | null>(null);
  const [dna, setDna] = useState<DecisionDNA | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDecision(null);
    setError(null);
    api.getDecision(decisionId).then(setDecision).catch((e) => setError(String(e)));
    api.getLineage(decisionId).then(setLineage).catch(() => {});
    api.getRisk(decisionId).then(setRisk).catch(() => {});
    api.getGovernance(decisionId).then(setGovernance).catch(() => {});
    api.getBoundary(decisionId).then(setBoundary).catch(() => {});
    api.getDna(decisionId).then(setDna).catch(() => {});
  }, [decisionId]);

  if (error) return <div className="error-banner">{error}</div>;
  if (!decision) return <div className="loading">Loading decision forensics for {decisionId}...</div>;

  return (
    <div>
      <div className="page-header">
        <h1>Decision Forensics -- {decision.decision_id}</h1>
        <div className="sub">
          {decision.system} &middot; {new Date(decision.timestamp).toISOString().replace("T", " ").slice(0, 19)} UTC &middot;{" "}
          <StatusBadge status={decision.replayability_status} />
        </div>
      </div>

      <div className="grid-metrics">
        <div className="metric-card"><div className="label">Outcome</div><div className="value"><OutcomeBadge outcome={decision.final_outcome} /></div></div>
        <div className="metric-card"><div className="label">Risk Score</div><div className="value accent">{decision.risk_score.toFixed(3)}</div></div>
        <div className="metric-card"><div className="label">Confidence</div><div className="value">{decision.confidence.toFixed(3)}</div></div>
        <div className="metric-card"><div className="label">Model</div><div className="value" style={{ fontSize: 14 }}>{decision.model_id}</div></div>
        <div className="metric-card"><div className="label">Policy</div><div className="value" style={{ fontSize: 14 }}>{decision.policy_id}</div></div>
        {risk && <div className="metric-card"><div className="label">Risk Level</div><div className="value" style={{ fontSize: 14 }}>{risk.risk_level}</div></div>}
        {boundary && (
          <div className="metric-card">
            <div className="label">Boundary</div>
            <div className="value" style={{ fontSize: 14 }}>
              {boundary.distance_to_block_threshold <= 0 ? "+" : ""}
              {(-boundary.distance_to_block_threshold).toFixed(3)} from BLOCK ({boundary.zone})
            </div>
          </div>
        )}
        {dna && <div className="metric-card"><div className="label">Integrity</div><div className="value" style={{ fontSize: 14 }}>{dna.integrity_status}</div></div>}
      </div>

      {dna && (
        <div className="panel" style={{ marginBottom: 20 }}>
          <div className="panel-header">Decision DNA</div>
          <div className="panel-body mono" style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>
{JSON.stringify(dna, null, 2)}
          </div>
        </div>
      )}

      <div className="two-col">
        <div>
          <div className="panel">
            <div className="panel-header">Evidence ({decision.evidence.length})</div>
            <div className="panel-body">
              {decision.evidence.map((e) => (
                <div className="evidence-row" key={e.evidence_id}>
                  <div className="evidence-id">{e.evidence_id}</div>
                  <div className="evidence-meta">
                    {e.kind} &middot; source: {e.source} &middot; classification: {e.classification}
                    <div className="mono" style={{ fontSize: 10, color: "var(--text-2)" }}>hash: {e.content_hash.slice(0, 16)}...</div>
                  </div>
                  <div style={{ width: 50, textAlign: "right", fontFamily: "var(--mono)" }}>{e.value.toFixed(2)}</div>
                  <div className="evidence-bar-track">
                    <div className="evidence-bar-fill" style={{ width: `${Math.round(e.value * 90)}px` }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">Tool Invocations</div>
            <div className="panel-body">
              <table>
                <thead><tr><th>Tool</th><th>Output</th><th>Deterministic</th></tr></thead>
                <tbody>
                  {decision.tool_invocations.map((t) => (
                    <tr key={t.tool_id} style={{ cursor: "default" }}>
                      <td className="mono">{t.tool_name}</td>
                      <td className="mono">{JSON.stringify(t.output)}</td>
                      <td>{t.deterministic ? <span style={{ color: "var(--ok)" }}>yes</span> : <span style={{ color: "var(--crit)" }}>no</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">Lineage Graph</div>
            <div className="panel-body">
              {lineage ? (
                <LineageView graph={lineage} />
              ) : (
                <div className="loading">Loading lineage...</div>
              )}
            </div>
          </div>
        </div>

        <div>
          <div className="panel">
            <div className="panel-header">Governance</div>
            <div className="panel-body">
              {governance?.map((f) => (
                <div key={f.control_id} style={{ marginBottom: 10, fontSize: 12 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span className="mono" style={{ fontWeight: 700 }}>{f.control_id} -- {f.control_name}</span>
                    <StatusBadge status={f.status} />
                  </div>
                  <div style={{ color: "var(--text-1)", marginTop: 3 }}>{f.reason}</div>
                </div>
              )) ?? <div className="loading">Loading governance...</div>}
            </div>
          </div>

          {risk && (
            <div className="panel">
              <div className="panel-header">Risk Assessment</div>
              <div className="panel-body">
                {Object.entries(risk.formulas).map(([key, formula]) => {
                  const val = (risk as any)[key];
                  return (
                    <div key={key} style={{ marginBottom: 8, fontSize: 11.5 }}>
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <span style={{ color: "var(--text-1)" }}>{key.replace(/_/g, " ")}</span>
                        <span className="mono" style={{ fontWeight: 700 }}>{val === null || val === undefined ? "n/a" : typeof val === "number" ? val.toFixed(3) : String(val)}</span>
                      </div>
                      <div style={{ color: "var(--text-2)", fontSize: 10 }}>{formula}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      <ReplayLab decisionId={decision.decision_id} evidence={decision.evidence} originalOutcome={decision.final_outcome} originalScore={decision.risk_score} />
      <ForensicSweep decisionId={decision.decision_id} originalOutcome={decision.final_outcome} originalScore={decision.risk_score} />
    </div>
  );
}

function LineageView({ graph }: { graph: LineageGraph }) {
  const byType: Record<string, typeof graph.nodes> = {};
  for (const n of graph.nodes) {
    byType[n.type] = byType[n.type] || [];
    byType[n.type].push(n);
  }
  const order = ["INPUT", "RETRIEVAL", "EVIDENCE", "MODEL", "POLICY", "CONTROL", "DECISION"];
  return (
    <div>
      {order.filter((t) => byType[t]).map((type, i) => (
        <div key={type} className="lineage-row">
          <span className="lineage-type" style={{ width: 64 }}>{type}</span>
          {byType[type].map((n) => (
            <span className="lineage-node" key={n.id}>{n.label}</span>
          ))}
          {i < order.length - 1 && byType[order[i + 1]] && <span className="lineage-arrow">&darr;</span>}
        </div>
      ))}
      <div style={{ color: "var(--text-2)", fontSize: 10.5, marginTop: 6 }}>
        {graph.edges.length} edges (DERIVED_FROM / USED_BY / EVALUATED_BY / GOVERNED_BY / RESULTED_IN)
      </div>
    </div>
  );
}
