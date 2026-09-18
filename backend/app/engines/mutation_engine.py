"""
backend/app/engines/mutation_engine.py

Generic mutation framework. A Mutation is a recorded, reversible transform on a
DecisionContext. Applying a mutation never touches the original Decision --
it produces a new context for the counterfactual engine to replay against.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from app.domain.enums import MutationType
from app.domain.models import DecisionContext, Evidence, ModelVersion, PolicyVersion


@dataclass(frozen=True)
class Mutation:
    mutation_id: str
    type: MutationType
    target: str
    before: str
    after: str
    reason: str
    actor: str = "investigator"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # payload carries the actual new value for ADD/MODIFY/CHANGE mutations
    payload: dict = field(default_factory=dict)


class MutationError(ValueError):
    pass


def apply_mutation(context: DecisionContext, mutation: Mutation) -> DecisionContext:
    """Return a NEW DecisionContext with the mutation applied. Original is untouched."""

    if mutation.type == MutationType.REMOVE_EVIDENCE:
        remaining = tuple(e for e in context.evidence if e.evidence_id != mutation.target)
        if len(remaining) == len(context.evidence):
            raise MutationError(f"Evidence '{mutation.target}' not found in context.")
        return replace(context, evidence=remaining)

    if mutation.type == MutationType.ADD_EVIDENCE:
        new_ev = Evidence(**mutation.payload).with_hash()
        return replace(context, evidence=context.evidence + (new_ev,))

    if mutation.type == MutationType.MODIFY_EVIDENCE:
        found = False
        new_evidence = []
        for e in context.evidence:
            if e.evidence_id == mutation.target:
                found = True
                merged = replace(e, **mutation.payload).with_hash()
                new_evidence.append(merged)
            else:
                new_evidence.append(e)
        if not found:
            raise MutationError(f"Evidence '{mutation.target}' not found in context.")
        return replace(context, evidence=tuple(new_evidence))

    if mutation.type == MutationType.CHANGE_POLICY:
        new_policy = PolicyVersion(**mutation.payload)
        return replace(context, policy_version=new_policy)

    if mutation.type == MutationType.CHANGE_MODEL:
        new_model = ModelVersion(**mutation.payload)
        return replace(context, model_version=new_model)

    if mutation.type == MutationType.CHANGE_THRESHOLD:
        field_name = mutation.payload.get("field", "block_threshold")
        new_value = float(mutation.payload["value"])
        new_policy = replace(context.policy_version, **{field_name: new_value})
        return replace(context, policy_version=new_policy)

    if mutation.type == MutationType.REMOVE_TOOL_RESULT:
        remaining = tuple(t for t in context.tool_invocations if t.tool_id != mutation.target)
        if len(remaining) == len(context.tool_invocations):
            raise MutationError(f"Tool invocation '{mutation.target}' not found in context.")
        return replace(context, tool_invocations=remaining)

    if mutation.type == MutationType.MODIFY_TOOL_RESULT:
        found = False
        new_tools = []
        for t in context.tool_invocations:
            if t.tool_id == mutation.target:
                found = True
                new_tools.append(replace(t, **mutation.payload))
            else:
                new_tools.append(t)
        if not found:
            raise MutationError(f"Tool invocation '{mutation.target}' not found in context.")
        return replace(context, tool_invocations=tuple(new_tools))

    if mutation.type == MutationType.CHANGE_INPUT:
        new_input = replace(context.input_snapshot, **mutation.payload).with_hash()
        return replace(context, input_snapshot=new_input)

    if mutation.type == MutationType.DISABLE_CONTROL:
        remaining = tuple(c for c in context.control_definitions if c.control_id != mutation.target)
        return replace(context, control_definitions=remaining)

    raise MutationError(f"Unsupported mutation type: {mutation.type}")


def apply_mutations(context: DecisionContext, mutations: list[Mutation]) -> DecisionContext:
    """Multi-variable counterfactual: fold mutations left-to-right."""
    ctx = context
    for m in mutations:
        ctx = apply_mutation(ctx, m)
    return ctx
