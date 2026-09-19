# Replay Integrity

## What it is

`backend/app/engines/integrity_engine.py` recomputes every content hash
this system actually tracks and compares each one against the value
recorded for it, surfacing drift as a machine-readable finding rather than
silently trusting the historical record.

```json
{
  "status": "COMPROMISED",
  "findings": [
    { "type": "EVIDENCE_HASH_MISMATCH", "target": "E3", "detail": "..." }
  ],
  "checked": ["input_snapshot:IN-001", "evidence:E1", "evidence:E2", "evidence:E3", "evidence:E4", "context"],
  "not_checked": ["model_version.weights (...)", "tool_invocations[*].output (...)"]
}
```

## What is genuinely checked, and how

- **Evidence**: each `Evidence.content_hash` is recomputed via
  `Evidence.with_hash()` from the item's current `value`/`weight`/`payload`
  and compared to the stored hash. Editing `value` without updating the
  hash is caught -- this is the exact "value tampered, hash stale" class of
  bug/attack.
- **Input snapshot**: same pattern via `InputSnapshot.with_hash()`.
- **Whole context, including model/policy identity**: `context_hash()`
  folds in the evidence hashes, the input hash, `model_version.model_id`
  and `policy_version.policy_id`. Comparing a freshly recomputed
  `context_hash()` against the value persisted at save time (a separate DB
  column, `DecisionRecord.context_hash`, never derived from the same blob
  being checked) catches a changed `model_id` or `policy_id` after the
  fact, even though `ModelVersion`/`PolicyVersion` have no dedicated hash
  field of their own.

## Status meaning

- `VERIFIED` -- everything checked matched.
- `COMPROMISED` -- at least one hash mismatch (`EVIDENCE_HASH_MISMATCH`,
  `INPUT_HASH_MISMATCH`, `CONTEXT_HASH_MISMATCH`). Proven drift.
- `UNKNOWN` -- no mismatch, but something couldn't be fully verified
  (`MISSING_HASH`, `MALFORMED_ARTIFACT` such as a NaN/Inf value). Not proven
  bad, but not vouched for either.

## What this does NOT guarantee

- **It does not prove the data was ever true.** If a value was wrong or
  forged *before* its hash was first computed, this check passes, because
  the hash and the (wrong) value have always matched. This is drift
  detection, not fact verification.
- **It is not a cryptographic signature scheme.** Nothing stops someone
  with direct DB write access from editing a value *and* its hash *and*
  the persisted context_hash column together, consistently. It catches
  sloppy/partial tampering (the far more common real-world case -- an
  edited field, a hand-patched record), not a fully self-consistent
  forgery by an attacker who also controls the hash fields.
- **Model weights and raw tool output are not independently hashed today.**
  `not_checked` says so explicitly on every call. Model/policy *identity*
  (their IDs) is covered indirectly through `context_hash()`, but a model's
  `weights` dict or a tool's `output` dict has no dedicated content_hash of
  its own to verify against.

## API

`GET /decisions/{id}/integrity`. Also feeds `DecisionDNA.integrity_status`
(`GET /decisions/{id}/dna`) -- when the API layer has a persisted
`context_hash` to compare against, DNA's integrity field is this real
check; only when built without one (e.g. an in-memory decision that was
never saved) does it fall back to a weaker replayability-only signal (see
`docs/decision-dna.md`).

## Tests

`backend/tests/test_integrity_engine.py` (12 tests): valid hashes, tampered
evidence value, changed input payload, changed policy_id after recording,
changed model_id after recording (both caught via context_hash), missing
hash, malformed (NaN) value, a partial-tamper case that flags only the
actually-tampered item, the "no stored hash supplied" skip path,
determinism, and the disclosed-gaps contract.
