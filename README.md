# RISK//REPLAY

**AI Decision Forensics & Counterfactual Replay Engine**

> Reconstruct the decision. Change the evidence. See what breaks.

**Live demo:** [jeevan-0508.github.io/risk-replay](https://jeevan-0508.github.io/risk-replay/)
(static build against a precomputed dataset, no backend required, see
[Static demo mode](#static-demo-mode) below). For the full dynamic backend, run it
locally: see [Quick start](#quick-start).

## The problem

Most AI-assisted systems can tell you what a decision was. Some can show you the logs
around it. Almost none can answer the question an investigator actually asks after an
incident:

> *"Here is the exact decision state, here is the evidence that influenced it, here is
> the policy and model state at that moment, here is what happens when we change one
> variable, and here is the resulting risk and governance impact."*

RISK//REPLAY is a small, serious engine built to answer exactly that question, and
nothing more.

## What it is not

Not a dashboard, not a chatbot, not an LLM wrapper, not a generic audit-log viewer.
There is no LLM anywhere in the decision path. The core is a deterministic rule engine
that is fully inspectable: every score in this system is defined by a formula in
`backend/app/engines/`, not inferred by a model.

## The core idea

```
DECISION -> EVIDENCE GRAPH -> LINEAGE -> DETERMINISTIC REPLAY -> MUTATION
    -> COUNTERFACTUAL REPLAY -> DIFF -> CAUSAL ANALYSIS -> RISK/GOVERNANCE -> REPORT
```

Every historical AI-assisted decision is stored as a frozen `DecisionContext`: the
input, the evidence used, the model version, the policy version, the tool calls, the
controls. Nothing about a replay ever reaches into current production state -- it
replays against exactly the historical snapshot it is given, or against a *mutated
copy* of that snapshot if you're running a counterfactual.

## The killer demo

`DEC-001` is a synthetic fraud-engine decision (all data below is fictional, generated
for this repo):

```
ORIGINAL DECISION
  Outcome:    BLOCK
  Score:      0.834   (policy-17 block threshold: 0.82)
  Model:      fraud-v3.2
  Policy:     policy-17
  Evidence:   E1 (velocity_signal) E2 (payment_history_risk)
              E3 (identity_risk)   E4 (device_mismatch)
```

Remove one evidence item (`E3`, the identity-risk signal) and replay:

```
COUNTERFACTUAL
  Outcome:    ALLOW
  Score:      0.549

DIVERGENCE:        YES
CHANGED VARIABLE:  Evidence E3
CAUSAL FINDING:    DECISION_CRITICAL under the replay model
GOVERNANCE IMPACT: Control C-17 (Human Oversight) status flips --
                    the decision no longer crosses the review threshold either
```

Put `E3` back, replay again: `BLOCK` returns, at exactly `0.834`, because the engine
is deterministic. Try it yourself:

```bash
curl -X POST localhost:8000/decisions/DEC-001/counterfactual \
  -H "Content-Type: application/json" \
  -d '{"mutations": [{"type": "REMOVE_EVIDENCE", "target": "E3", "reason": "investigate"}]}'
```

## Second demo: policy impact replay

"What would have happened if we'd deployed `policy-18` yesterday?"

```bash
curl -X POST localhost:8000/policies/policy-18/impact-replay \
  -H "Content-Type: application/json" \
  -d '{"policy_id":"policy-18","block_threshold":0.75,"review_threshold":0.45,"required_controls":["C-17","C-08"]}'
```

Against the 40-decision golden dataset this replays every historical decision under
the new thresholds and reports exactly how many outcomes change, how many now require
human review, and which specific decisions moved.

## Architecture

```
        WEB UI  (React/Vite, minimal -- see frontend/)
           |
        REST API (FastAPI)
           |
  Decision Store / Event Store / Policy & Model Registry   (SQLAlchemy -> Postgres or SQLite)
           |
  Lineage -> Replay -> Mutation -> Counterfactual -> Diff -> Risk -> Governance -> Incident
  (backend/app/engines/*.py -- pure, deterministic, zero SQL, zero HTTP, zero LLM calls)
```

The engines never import SQLAlchemy or FastAPI. They operate purely on the frozen
dataclasses in `backend/app/domain/models.py`. This is deliberate: it's what makes the
backend independently testable and what makes "the core does not depend on an LLM" an
enforceable structural fact rather than a promise.

## Failure is a feature

Not every decision can be perfectly reconstructed. RISK//REPLAY has an explicit
`ReplayabilityStatus`: `REPLAYABLE`, `PARTIALLY_REPLAYABLE`, `NON_REPLAYABLE`, each with
a machine-readable reason (`MISSING_MODEL_VERSION`, `NON_DETERMINISTIC_TOOL`, etc). A
forensic system that confidently invents an answer is worse than one that says "this
cannot be reconstructed, here's why." See `docs/failure-modes.md`.

Same discipline applies to causal language: the causal engine never claims real-world
certainty. A single-variable flip is reported as `DECISION_CRITICAL under the replay
model`, not "the true cause." See `docs/methodology.md`.

## Quick start

```bash
cd backend
uv sync                     # or: pip install -r requirements.txt
python -m app.seed          # loads the 40-decision golden dataset + demo incident
uv run uvicorn app.api.main:app --reload   # http://localhost:8000
```

Run the tests:

```bash
cd backend
python -m pytest -q         # 34 tests: unit, integration, property-based
```

## Static demo mode

GitHub Pages only serves static files, it can't run the Python backend, so the live
demo above ships a client-side build: `backend/scripts/dump_static_bundle.py` runs the
real engines once against the golden dataset and freezes the output to
`frontend/public/data/bundle.json`, and `frontend/src/staticEngine.ts` is a line-for-line
TypeScript port of the decision/mutation/diff/causal engines so the Replay Lab's
counterfactual feature stays genuinely interactive (build a mutation, it actually gets
evaluated, not looked up from a fixed list). `frontend/src/api.ts` picks this
(`VITE_STATIC=true`) or the real backend (`liveApi.ts`, default in dev) at build time.
Verified the TS port reproduces the exact backend numbers for the golden scenario and
for multi-variable mutations before deploying.

The dynamic backend (persistence, incidents, policy-impact-replay, arbitrary decisions
beyond the golden dataset) only runs locally -- see Quick start below.

## What's built vs. what's deferred

Built and tested end-to-end against real persisted data:
- Domain model, deterministic decision engine, replay engine with replayability
  assessment, mutation engine (9 mutation types), counterfactual engine, diff engine,
  causal engine, risk engine, governance engine, incident reconstruction, blast radius,
  policy-impact replay.
- Full REST API (`backend/app/api/main.py`) -- every route calls a real engine, nothing
  hardcoded.
- 40-decision golden dataset, event log, SQLite by default / Postgres-ready.
- 34 automated tests: unit, API integration, and Hypothesis property-based
  (`Replay(original) == original`, remove-then-restore round-trips, threshold mutations
  never leave `[0,1]`).

Deliberately deferred (see `docs/` for the honest list, not hidden):
- Full 10-screen forensic UI -- v1 ships Command Center, Decision Vault, Decision
  Forensics, and the Replay/Mutation Lab (the killer feature), wired to the real API.
  Timeline, Evidence Graph visualization, and Incident Console are backend-complete
  (real endpoints, real data) but not yet given dedicated screens.
- PII redaction / field-level masking engine.
- Full adversarial test suite (forged evidence, replay poisoning) -- covered
  conceptually in `docs/threat-model.md`, not yet as executable tests.

## Docs

- `docs/architecture.md` -- component map and why
- `docs/replay-model.md` -- what determinism means here, and its limits
- `docs/counterfactual-engine.md` -- mutation + counterfactual mechanics
- `docs/decision-lineage.md` -- the lineage graph
- `docs/governance-engine.md`, `docs/risk-engine.md` -- formulas
- `docs/methodology.md` -- causal language rules
- `docs/failure-modes.md` -- non-replayability, explicitly
- `docs/security.md`, `docs/threat-model.md` -- what provenance hashing does and does
  not guarantee

## Disclosure

All data in this repository (`app/golden_dataset.py`) is synthetic and fictional,
generated for demonstration. No real transactions, accounts, or personal data.
