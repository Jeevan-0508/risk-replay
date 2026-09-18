# Threat Model

| Threat | Current posture |
|---|---|
| Forged evidence | Content-hashed at ingestion; a forged item still gets its own valid hash of forged content -- hashing detects *tampering after storage*, not forgery *before* storage. Ingestion-time validation against a trusted source is out of scope for v1. |
| Timestamp manipulation | Timestamps are accepted as given at ingestion; no monotonicity or clock-skew check yet. |
| Replay poisoning (feeding a replay a mutated context and presenting it as the original) | Structurally prevented for the counterfactual flow: `run_counterfactual` always replays the *decision's own stored context* as the baseline and a freshly-derived mutated copy as the counterfactual, in the same call -- a caller cannot substitute an arbitrary "original." |
| Model/policy version mismatch | `assess_replayability` fails closed (`NON_REPLAYABLE`) if the bound model or policy id is empty; it does not currently cross-check against a registry of "known good" versions -- see `/models`, `/policies` registries, which exist but aren't yet enforced at replay time. |
| Cross-tenant access | Not applicable -- no multi-tenancy in v1. |
| PII leakage | `EvidenceClassification` (`PUBLIC`/`INTERNAL`/`SENSITIVE`/`RESTRICTED`) is modeled on every evidence item but nothing currently redacts or masks `SENSITIVE`/`RESTRICTED` fields in API responses. Flagged in the README as deferred, not silently skipped. |
| Malicious tool output | Tool outputs are treated as immutable replay inputs (see security.md); no sandboxing needed because replay never executes a tool, it only reads recorded output. |
| Prompt injection | No LLM is in the decision path, so there is no prompt to inject into for the core engine. If an LLM-assist summarization feature is added later, evidence payloads must be treated as untrusted text at that boundary. |
| Unauthorized replay | No authN/authZ in v1 -- every endpoint is open. Documented as a hard limitation, not a hidden gap. |
