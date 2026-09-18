# STATUS (as of 2026-09-18, session 1)

## Shipped, tested, pushed
- Backend engine (domain, decision/replay/mutation/counterfactual/diff/causal/risk/
  governance engines) -- 100% pure Python, zero SQL/HTTP/LLM in the engine layer.
- FastAPI app with every route calling a real engine/repository, zero hardcoded
  responses. SQLite by default, Postgres-ready via `DATABASE_URL`.
- 40-decision synthetic golden dataset + seed script + 1 demo incident.
- 34 automated tests (unit, API integration via FastAPI TestClient, Hypothesis
  property-based). All passing as of last run this session.
- Killer demo (`DEC-001`, remove evidence E3, BLOCK -> ALLOW, DECISION_CRITICAL) verified
  three ways: unit test, API integration test, and a live curl call against a running
  server.
- Policy-impact-replay (`policy-17` -> `policy-18` across all 40 decisions) verified
  live via curl: 12 changed, 11 requiring review, 28 unchanged.
- Frontend (React + TS + Vite): Command Center, Decision Vault, Decision Forensics
  (evidence/tools/lineage/governance/risk), Replay Lab / Mutation Lab (the killer
  feature UI). Fixed a real bug this session: type-only imports from `api.ts` need
  `import type` under this project's bundler (rolldown-vite via bun) or the module
  fails to load at runtime with "does not provide an export named X". Also fixed:
  browser fetch needs `127.0.0.1`, not `localhost`, in this sandbox.
- Repo live: `github.com/Jeevan-0508/risk-replay`, 3 commits, README with the real
  demo walkthrough, `docs/` with architecture/replay-model/counterfactual-engine/
  decision-lineage/risk-engine/governance-engine/methodology/failure-modes/security/
  threat-model.

## Verified but with one caveat
The frontend was confirmed rendering correctly via `document.getElementById('root').innerText`
checks in-session (full sidebar + view content appeared after the import fix). The
in-session browser tool then stopped responding (timeouts on every subsequent call) --
so there is no final full-page screenshot from this session. Code is type-checked clean
(`tsc --noEmit`) and the API wiring is unit/integration-tested on the backend side; a
visual pixel-check with a fresh browser session is the one item to do first next time,
before treating the UI as fully verified.

## Deferred, honestly, not hidden (see README "What's built vs deferred")
- Timeline, Evidence Graph (dedicated interactive viz), Incident Console, Governance
  Impact, Policy Impact Replay screens -- backend endpoints exist and are tested;
  no dedicated UI yet.
- PII redaction / field-level masking.
- Adversarial test suite (forged evidence, replay poisoning) as executable tests --
  covered conceptually in docs/threat-model.md only.
- Auth/authz -- none in v1, documented as a hard limit in docs/security.md.
- `CausalStatus.NON_DETERMINATIVE` / `INSUFFICIENT_EVIDENCE` are defined but not yet
  emitted by `causal_engine.analyze()` -- see docs/methodology.md.

## Next session should start with
1. Fresh browser session: `browser navigate http://127.0.0.1:5173/` against a freshly
   started backend+frontend, confirm the killer demo visually end to end, screenshot it.
2. Pick 1-2 of the deferred screens (Policy Impact Replay UI is probably highest value --
   the backend endpoint is done and it's a strong second demo) rather than trying to
   build all remaining screens at once.
3. If continuing multi-session: this file is the handoff. Confirm `git log --oneline`
   matches `dce237e` (or later) before resuming.
