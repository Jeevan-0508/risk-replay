# RISK//REPLAY frontend

Minimal forensic console UI, wired to the real API (no mock data). Ships four screens
in v1:

- **Command Center** -- aggregate metrics computed live from `/decisions`
- **Decision Vault** -- searchable/filterable decision list
- **Decision Forensics** -- evidence, tool invocations, lineage graph, governance
  findings, risk formulas for one decision
- **Replay Lab / Mutation Lab** -- the killer feature: build a mutation, run
  `/decisions/{id}/counterfactual`, see the original vs counterfactual outcome, the
  causal finding, and a field-level diff

## Run

```bash
bun install     # or npm install
bun run dev     # http://localhost:5173, expects the API on http://127.0.0.1:8000
```

Set `VITE_API_BASE` in `.env.development` if the API runs elsewhere. Note: use
`127.0.0.1`, not `localhost`, if you hit fetch failures in a sandboxed browser context
that doesn't resolve `localhost`.

## Deferred (not built yet, not faked)

Timeline view, dedicated Evidence Graph visualization (data is served correctly by
`/decisions/{id}/lineage`, just not given its own interactive graph screen yet),
Incident Console, Governance Impact screen, Policy Impact Replay screen (the endpoint
works, see `docs/`, no UI yet). All of these are one real API call away -- the gap is
screens, not backend capability.
