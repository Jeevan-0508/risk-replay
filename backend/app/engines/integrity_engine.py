"""
backend/app/engines/integrity_engine.py

REPLAY INTEGRITY: verifies that the historical artifacts a decision claims
to be built from still match the content hashes recorded for them.

What this DOES guarantee:
  - stable_hash() (see domain/models.py) is a deterministic SHA-256 over a
    canonical JSON encoding of specific fields. If any of those fields
    change without the hash being recomputed, re-deriving the hash here and
    comparing it to the stored one will disagree -- this catches "value was
    edited but the hash wasn't updated to match", the exact class of bug or
    attack this replaces manual auditing for.
  - The same applies at the whole-context level via `context_hash()`, which
    folds in evidence hashes, the input hash, the model id and the policy
    id. Changing model_id or policy_id after the decision was recorded (a
    classic "context tampering" attack) changes context_hash() and is
    caught the same way, even though ModelVersion/PolicyVersion do not have
    their own dedicated hash fields.

What this DOES NOT guarantee (see docs/integrity.md for the full scope):
  - It does not prove the original hash was ever trustworthy -- if the data
    was wrong or forged *before* the hash was first computed, this check
    passes anyway. It only detects drift after the fact.
  - It is not a cryptographic signature scheme: nothing here prevents
    someone with DB write access from editing BOTH the value and the hash
    together. It detects sloppy/partial tampering, not a fully consistent
    forgery.
  - ModelVersion, PolicyVersion and ToolInvocation.output do not carry
    their own dedicated content_hash fields today. Model/policy identity
    IS covered indirectly (see above), but there is no direct field-level
    hash for a model's weights or a tool's raw output. That gap is reported
    explicitly via `not_checked`, never silently assumed clean.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.domain.models import Decision


@dataclass(frozen=True)
class IntegrityFinding:
    finding_type: str  # e.g. "EVIDENCE_HASH_MISMATCH", "MISSING_HASH", "MALFORMED_ARTIFACT", "CONTEXT_HASH_MISMATCH"
    target: str
    detail: str

    def to_dict(self) -> dict:
        return {"type": self.finding_type, "target": self.target, "detail": self.detail}


@dataclass(frozen=True)
class IntegrityReport:
    status: str  # "VERIFIED" | "COMPROMISED" | "UNKNOWN"
    findings: tuple[IntegrityFinding, ...]
    checked: tuple[str, ...]
    not_checked: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "findings": [f.to_dict() for f in self.findings],
            "checked": list(self.checked),
            "not_checked": list(self.not_checked),
        }


_NOT_CHECKED = (
    "model_version.weights (no dedicated content_hash field; identity is covered "
    "indirectly via context_hash, but the weights themselves are not independently hashed)",
    "tool_invocations[*].output (no dedicated content_hash field; not independently hashed)",
)


def verify_integrity(decision: Decision, stored_context_hash: str | None = None) -> IntegrityReport:
    """Recompute every content hash this system actually tracks and compare
    against the value stored on the artifact (or, for the whole context,
    against `stored_context_hash` -- the value persisted at save time,
    passed in by the caller since engines never touch the DB directly).

    `stored_context_hash=None` means the caller has no persisted value to
    compare against (e.g. a decision built in-memory, not yet saved) --
    the context-level check is then simply skipped, not silently passed.
    """
    findings: list[IntegrityFinding] = []
    checked: list[str] = []
    context = decision.context

    input_snap = context.input_snapshot
    checked.append(f"input_snapshot:{input_snap.input_id}")
    if not input_snap.content_hash:
        findings.append(IntegrityFinding("MISSING_HASH", input_snap.input_id, "Input snapshot has no recorded content_hash."))
    else:
        recomputed = input_snap.with_hash().content_hash
        if recomputed != input_snap.content_hash:
            findings.append(IntegrityFinding(
                "INPUT_HASH_MISMATCH", input_snap.input_id,
                "Recomputing the hash from the current payload does not match the recorded content_hash.",
            ))

    for ev in context.evidence:
        checked.append(f"evidence:{ev.evidence_id}")
        if isinstance(ev.value, float) and (math.isnan(ev.value) or math.isinf(ev.value)):
            findings.append(IntegrityFinding("MALFORMED_ARTIFACT", ev.evidence_id, f"Evidence value is not a finite number ({ev.value})."))
            continue
        if not ev.content_hash:
            findings.append(IntegrityFinding("MISSING_HASH", ev.evidence_id, "Evidence item has no recorded content_hash."))
            continue
        recomputed = ev.with_hash().content_hash
        if recomputed != ev.content_hash:
            findings.append(IntegrityFinding(
                "EVIDENCE_HASH_MISMATCH", ev.evidence_id,
                "Recomputing the hash from the current value/weight/payload does not match the recorded content_hash.",
            ))

    if stored_context_hash is not None:
        checked.append("context")
        recomputed_context_hash = context.context_hash()
        if recomputed_context_hash != stored_context_hash:
            findings.append(IntegrityFinding(
                "CONTEXT_HASH_MISMATCH", decision.decision_id,
                "Recomputed context_hash does not match the hash persisted when this decision was recorded. "
                "This is also how a changed model_id or policy_id after recording is caught.",
            ))

    mismatch_types = {"EVIDENCE_HASH_MISMATCH", "INPUT_HASH_MISMATCH", "CONTEXT_HASH_MISMATCH"}
    if any(f.finding_type in mismatch_types for f in findings):
        status = "COMPROMISED"
    elif findings:  # only MISSING_HASH / MALFORMED_ARTIFACT -- can't fully vouch, but no proven tamper either
        status = "UNKNOWN"
    else:
        status = "VERIFIED"

    return IntegrityReport(
        status=status,
        findings=tuple(findings),
        checked=tuple(checked),
        not_checked=_NOT_CHECKED,
    )
