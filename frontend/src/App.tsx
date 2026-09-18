import { useState } from "react";
import { CommandCenter } from "./views/CommandCenter";
import { DecisionVault } from "./views/DecisionVault";
import { DecisionForensics } from "./views/DecisionForensics";

type View = "command-center" | "vault" | "forensics";

export default function App() {
  const [view, setView] = useState<View>("command-center");
  const [decisionId, setDecisionId] = useState<string | null>(null);

  function openDecision(id: string) {
    setDecisionId(id);
    setView("forensics");
  }

  return (
    <div className="app-shell">
      <div className="sidebar">
        <div className="brand">
          <div className="title">RISK<span className="slash">//</span>REPLAY</div>
          <div className="tagline">Reconstruct the decision.<br />Change the evidence.<br />See what breaks.</div>
        </div>

        <div className="nav-section-label">Investigate</div>
        <div className={`nav-item ${view === "command-center" ? "active" : ""}`} onClick={() => setView("command-center")}>Command Center</div>
        <div className={`nav-item ${view === "vault" ? "active" : ""}`} onClick={() => setView("vault")}>Decision Vault</div>
        <div className={`nav-item ${view === "forensics" ? "active" : ""}`} onClick={() => decisionId && setView("forensics")}>
          Decision Forensics {decisionId ? `(${decisionId})` : ""}
        </div>

        <div style={{ marginTop: "auto", padding: "12px 16px", color: "var(--text-2)", fontSize: 10 }}>
          v0.1.0 &middot; synthetic demo data<br />no LLM in decision path
        </div>
      </div>

      <div className="main">
        {view === "command-center" && <CommandCenter onOpenDecision={openDecision} />}
        {view === "vault" && <DecisionVault onOpenDecision={openDecision} />}
        {view === "forensics" && decisionId && <DecisionForensics decisionId={decisionId} />}
        {view === "forensics" && !decisionId && <div className="empty-state">Open a decision from the Command Center or Decision Vault.</div>}
      </div>
    </div>
  );
}
