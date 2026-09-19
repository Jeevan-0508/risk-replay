# Decision DNA

## What it is

A deterministic, human-readable summary of a decision's forensic
structure (`backend/app/engines/dna_engine.py`). Not an embedding, not a
model output -- every field is either a recorded fact or a value computed
by an existing engine.

```json
{
  "decision_id": "DEC-001",
  "model": "fraud-v3.2",
  "policy": "policy-17",
  "baseline_score": 0.834,
  "outcome": "BLOCK",
  "boundary_margin": -0.014,
  "zone": "BLOCK",
  "replayability": "REPLAYABLE",
  "evidence_count": 4,
  "decision_critical_variables": ["E1", "E2", "E3", "E4"],
  "governance_affected_controls": ["C-17"],
  "integrity_status": "VERIFIED"
}
```

## Field provenance

| Field | Source |
|---|---|
| `model`, `policy`, `baseline_score`, `outcome`, `evidence_count` | Recorded on the `Decision` at decision time |
| `boundary_margin`, `zone` | `boundary_engine.analyze()` |
| `replayability` | `replay_engine.replay()` |
| `decision_critical_variables`, `governance_affected_controls` | A Forensic Sweep result, if supplied |
| `integrity_status` | Derived from replayability (see limitation below) |

## The "no sweep supplied" contract

`build_dna()` takes an *optional* `sweep` argument. If no sweep is
supplied, `decision_critical_variables` and `governance_affected_controls`
are `null` -- explicitly "not computed" -- never a fabricated empty list
that would read as "nothing here is critical". `GET /decisions/{id}/dna`
always runs a fresh in-memory sweep (pure, deterministic, not persisted by
that call) so the served DNA never has to guess.

## Honest limitation: `integrity_status`

This field is currently derived **only** from whether the decision
replayed (`REPLAYABLE` -> `VERIFIED`, `PARTIALLY_REPLAYABLE` -> `PARTIAL`,
`NON_REPLAYABLE` -> `UNKNOWN`). It is **not** a cryptographic
tamper-detection verdict. A decision whose evidence was silently altered
without updating its recorded hash would still show `VERIFIED` here,
because nothing in this engine re-verifies hashes yet. A genuine
hash-verification integrity layer is a separate, not-yet-built capability
-- do not read `integrity_status` as proof the underlying data is
untampered.

## API

`GET /decisions/{id}/dna` (query param `approved_model`, default
`fraud-v3.2`).

## Tests

`backend/tests/test_dna_engine.py` (5 tests): fields without a sweep are
explicit `None`; fields with a sweep report the real DEC-001 critical
variables and affected controls; boundary margin matches
`boundary_engine`; determinism (same inputs -> byte-identical output);
full key-set contract.
