import { useState } from "react";
import { toRiskReplayHandoff, validateSwarmResearchCapture, type SwarmResearchCapture } from "../researchCapture";

export function ResearchCaptureReview() {
  const [capture, setCapture] = useState<SwarmResearchCapture | null>(null);
  const [fileName, setFileName] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function readFile(file: File | null) {
    setCapture(null);
    setFileName(null);
    setError(null);
    if (!file) return;
    if (file.size === 0 || file.size > 2_000_000) {
      setError("Choose a non-empty JSON file no larger than 2 MB.");
      return;
    }
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const result = validateSwarmResearchCapture(parsed);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setCapture(result.capture);
      setFileName(file.name);
    } catch (cause) {
      setError(cause instanceof Error ? `Could not read capture: ${cause.message}` : "Could not read capture JSON.");
    }
  }

  function downloadMeshHandoff() {
    if (!capture) return;
    const handoff = toRiskReplayHandoff(capture, new Date().toISOString());
    const blob = new Blob([JSON.stringify(handoff, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `risk-replay-handoff-${capture.research.run_id}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  return (
    <div>
      <div className="page-header">
        <h1>Research Capture Review</h1>
        <div className="sub">Inspect a frozen SWARM retrieval capture, then create a manual handoff for MESH.</div>
      </div>

      <div className="panel">
        <div className="panel-body">
          <div className="warning-banner">
            This page validates and displays a research snapshot. It does not re-run retrieval, create a decision, or prove that a source is authentic or true. The file stays in this browser; no API request or database write is made.
          </div>
          <label style={{ display: "block", marginTop: 16, fontSize: 12 }}>
            Select a <span className="mono">swarm-research-capture.v1</span> JSON file (maximum 2 MB)
            <input type="file" accept=".json,application/json" style={{ display: "block", marginTop: 8 }} onChange={(event) => {
              const file = event.currentTarget.files?.[0] ?? null;
              event.currentTarget.value = "";
              void readFile(file);
            }} />
          </label>
          {error && <div className="error-banner" role="alert" style={{ marginTop: 14 }}>{error}</div>}
        </div>
      </div>

      {capture && (
        <>
          <div className="panel" style={{ marginTop: 16 }}>
              <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span>Capture summary</span><span className="mono">UNREVIEWED · NOT REPLAYED</span></div>
            <div className="panel-body">
              <div className="research-handoff-sub">Loaded locally from {fileName}</div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: 12, marginTop: 14 }}>
                <div><div className="research-handoff-label">SWARM run id</div><div className="mono">{capture.research.run_id}</div></div>
                <div><div className="research-handoff-label">retrieval status</div><div className="mono">{capture.research.retrieval_status}</div></div>
                <div><div className="research-handoff-label">attempts / source records</div><div className="mono">{capture.research.attempts.length} / {capture.research.source_records.length}</div></div>
                <div><div className="research-handoff-label">source revision</div><div className="mono">{capture.source.revision ?? "unknown"}</div></div>
              </div>
              <div style={{ marginTop: 14 }}><div className="research-handoff-label">operator-supplied question</div><p>{capture.research.question || "(empty)"}</p></div>
              {capture.research.attempts.length > 0 && <div style={{ marginTop: 14 }}>
                <div className="research-handoff-label">retrieval attempts · failures remain visible</div>
                {capture.research.attempts.map((attempt, i) => <div key={`${attempt.provider}-${i}`} className="mono" style={{ marginTop: 6, fontSize: 11 }}>
                  {attempt.provider} · {attempt.status} · retained {attempt.retained}/{attempt.returned} · {attempt.reason ?? "no error reported"}
                </div>)}
              </div>}
            </div>
          </div>

          <div className="panel" style={{ marginTop: 16 }}>
            <div className="panel-header"><span>External source records · content, not verified claims</span><span className="mono">{capture.research.source_records.length}</span></div>
            <div className="panel-body" style={{ padding: 0 }}>
              {capture.research.source_records.length === 0 ? <div className="empty-state">No external source records were retained in this capture.</div> : capture.research.source_records.map((source) => (
                <article key={source.evidence_id} style={{ borderBottom: "1px solid var(--border)", padding: 14 }}>
                  <div className="mono" style={{ fontSize: 10, color: "var(--text-2)" }}>{source.evidence_id} · {source.provider} · {source.data_class}</div>
                  <div style={{ marginTop: 5 }}>{source.title || "(untitled source record)"}</div>
                  <div className="research-handoff-sub" style={{ marginTop: 4 }}>{source.source_identity} · retrieved {source.retrieved_at} · stated date {source.stated_date ?? "unknown"} ({source.date_kind})</div>
                  <p style={{ marginTop: 8, fontSize: 12 }}>{source.excerpt || "(no excerpt)"}</p>
                  <a href={source.url} target="_blank" rel="noreferrer">Open source</a>
                  {source.caveats.length > 0 && <div className="research-handoff-sub" style={{ marginTop: 7 }}>Limits: {source.caveats.join(" · ")}</div>}
                  <div className="research-handoff-sub" style={{ marginTop: 5 }}>Fingerprint: {source.content_hash_algorithm} · this does not verify source identity or truth.</div>
                </article>
              ))}
            </div>
          </div>

          <div className="panel" style={{ marginTop: 16 }}>
            <div className="panel-header" style={{ display: "flex", justifyContent: "space-between", gap: 12 }}><span>Synthetic hypothesis context</span><span className="mono">{capture.hypothesis_context ? "SYNTHETIC · UNVERIFIED" : "NOT ATTACHED"}</span></div>
            <div className="panel-body">
              {capture.hypothesis_context ? <>
                <div className="warning-banner">This Fraud Watch candidate is simulator output only. It is never a source record, a real incident, a validated claim, or knowledge ready for promotion.</div>
                <div className="mono" style={{ marginTop: 10 }}>{String((capture.hypothesis_context.candidate.candidate as Record<string, unknown>).id ?? "candidate id unavailable")}</div>
                <div className="research-handoff-sub" style={{ marginTop: 5 }}>seed {String((capture.hypothesis_context.candidate.simulation as Record<string, unknown>).seed ?? "unknown")} · authenticity {capture.hypothesis_context.authenticity}</div>
              </> : <div className="research-handoff-sub">No simulator hypothesis was included in this capture.</div>}
            </div>
          </div>

          <div className="panel" style={{ marginTop: 16 }}>
            <div className="panel-body">
              <div className="warning-banner">The handoff will remain explicitly unreviewed and not replayed. It carries the same separate source-record and synthetic-context fields to MESH; it does not approve claims or knowledge changes.</div>
              <button className="btn" style={{ marginTop: 12 }} onClick={downloadMeshHandoff}>Download unreviewed MESH handoff</button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
