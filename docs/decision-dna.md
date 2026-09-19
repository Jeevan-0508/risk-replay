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

## `integrity_status`

**Updated**: `integrity_status` now comes from a real Replay Integrity
check (`integrity_engine.verify_integrity`, see `docs/integrity.md`) when
the caller supplies a persisted `context_hash` to compare against --
which `GET /decisions/{id}/dna` always does. It genuinely detects a
tampered evidence value, a tampered input payload, or a changed
model_id/policy_id after the fact.

Remaining honest limits (see `docs/integrity.md` for the full scope): it
does not prove the original data was ever true (only that it hasn't
drifted since its hash was first computed), it is not a cryptographic
signature scheme, and model weights / raw tool output are not
independently hashed.

**Static demo (GitHub Pages) note**: the browser-side TS port does not
include a client-side integrity check. The static bundle is a frozen,
already-trusted snapshot with nothing tampering it at runtime, so a ported
hash-verification would always trivially return `VERIFIED` -- there is no
adversary in that context for it to catch anything against. The static
demo's DNA panel falls back to the replayability-only signal for this
field; this is a deliberate, disclosed scope boundary, not an oversight.

## API

`GET /decisions/{id}/dna` (query param `approved_model`, default
`fraud-v3.2`).

## Tests

`backend/tests/test_dna_engine.py` (5 tests): fields without a sweep are
explicit `None`; fields with a sweep report the real DEC-001 critical
variables and affected controls; boundary margin matches
`boundary_engine`; determinism (same inputs -> byte-identical output);
full key-set contract.
