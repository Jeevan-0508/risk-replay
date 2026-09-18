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

## Deployed (session 2, same day)
**Live: https://jeevan-0508.github.io/risk-replay/**

GitHub Pages only serves static files and can't run the Python backend, so instead of
standing up a separate host (Render/Railway all need a new account signup), the
deterministic engines were ported to TypeScript (`frontend/src/staticEngine.ts`) and a
full data bundle precomputed from the real Python engines
(`backend/scripts/dump_static_bundle.py` -> `frontend/public/data/bundle.json`, 40
decisions). `frontend/src/api.ts` branches between `liveApi.ts` (dev, real backend) and
`staticApi.ts` (`VITE_STATIC=true` production build). The Replay Lab stays fully
interactive with zero backend: build any REMOVE_EVIDENCE / CHANGE_THRESHOLD mutation,
it's genuinely evaluated by the TS engine, not looked up from a fixed list.

Verified three ways before calling it done:
1. Standalone script ran the TS engine against the bundle and asserted it reproduces
   the exact backend numbers (0.834 BLOCK -> 0.549 ALLOW removing E3, plus multi-variable
   CONTRAFACTUAL wording, plus bad-target error handling).
2. `tsc --noEmit` clean, `bun run build` succeeds, dist assets confirmed reachable
   through the live GitHub Pages CDN (HTML, JS, CSS, bundle.json all 200).
3. **Live browser session against the actual deployed URL**: navigated, opened DEC-001,
   added a REMOVE_EVIDENCE mutation on E3 through the real UI, clicked Run
   Counterfactual, confirmed via `browser content` that the page displayed
   BLOCK 0.834 -> ALLOW 0.549, DECISION_CRITICAL, exactly matching the golden numbers.
   No pixel screenshot was possible (browser panel not visible in this environment this
   session), but the functional check is definitive: real data, real click, real
   computed result, not a mock.
4. Deploy path: pushed a `gh-pages` branch (orphan, contains only `dist/`) via a git
   worktree, enabled Pages via the GitHub API pointed at that branch, then had to
   manually POST `/pages/builds` once because switching the `source` via PATCH didn't
   auto-trigger a rebuild.

## Next session should start with
1. Pick 1-2 of the deferred screens (Policy Impact Replay UI is probably highest value --
   the backend endpoint is done and it's a strong second demo) rather than trying to
   build all remaining screens at once. If adding a new screen, remember it needs data in
   `bundle.json` too if it's meant to work on the static Pages demo -- update
   `dump_static_bundle.py` and rerun it before rebuilding the frontend.
2. If continuing multi-session: this file is the handoff. Confirm `git log --oneline`
   matches this commit (or later) before resuming.
