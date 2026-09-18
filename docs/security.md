# Security Model

## What content hashing actually proves

`stable_hash()` (SHA-256 over a sorted-key JSON encoding) proves: *this exact byte
content is what's stored under this evidence/input id right now.* It does **not**
prove the content is true, and it does **not** prove nobody could have forged it before
it reached this system. Hashing here is a tamper-evidence mechanism for content already
inside RISK//REPLAY, not a cryptographic attestation of the outside world.

## Replay isolation

Replays and counterfactuals only ever operate on `DecisionContext` objects already
loaded into memory -- there is no code path from `replay()` or `apply_mutation()` back
out to a live tool, model endpoint, or database write against production systems. A
"non-deterministic tool" mutation type does not re-invoke anything; it only lets an
investigator simulate what a different tool output would have implied.

## Threat model (see docs/threat-model.md for detail)

Considered: forged evidence at ingestion, timestamp manipulation, cross-tenant access,
malicious tool output at ingestion time, prompt injection via evidence payloads reaching
any future LLM-assist feature. **Not yet implemented**: authentication/authorization
(there is none in this v1 -- every endpoint is open), tenant isolation, and rate
limiting. This is a single-tenant demo/portfolio system; do not deploy it multi-tenant
or on real personal data without adding those.
