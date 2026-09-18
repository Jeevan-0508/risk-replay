import { createRoot } from "react-dom/client";
import "./index.css";
import { Component, type ReactNode } from "react";
import App from "./App";

/**
 * A UI-level render error is data, not something to hide behind a white
 * screen -- consistent with the product's core principle that failure
 * states must be surfaced explicitly, never swallowed.
 */
class ErrorBoundary extends Component<{ children: ReactNode }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: String((e as Error)?.stack || e) };
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 24, fontFamily: "monospace", color: "#ff5c33", background: "#0a0c0f", height: "100vh" }}>
          <div style={{ fontWeight: 700, marginBottom: 10 }}>RISK//REPLAY UI FAILURE</div>
          <pre style={{ whiteSpace: "pre-wrap", color: "#e8ebef" }}>{this.state.error}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>,
);
