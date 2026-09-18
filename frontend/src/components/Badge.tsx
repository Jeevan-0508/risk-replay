export function OutcomeBadge({ outcome }: { outcome: string }) {
  const cls = outcome === "BLOCK" ? "badge-block" : outcome === "ALLOW" ? "badge-allow" : "badge-review";
  return <span className={`badge ${cls}`}>{outcome}</span>;
}

export function StatusBadge({ status }: { status: string }) {
  const cls = `badge-${status.toLowerCase()}`;
  return <span className={`badge ${cls}`}>{status.replace(/_/g, " ")}</span>;
}
