# Architecture

## Layering

```
app/api/        FastAPI routes + Pydantic schemas. Talks to repository + engines.
app/engines/     Pure functions over domain dataclasses. No SQL, no HTTP, no LLM calls.
app/domain/      Frozen dataclasses (Decision, DecisionContext, Evidence, ...) + enums.
app/db/          SQLAlchemy ORM models, session management, serialization, repository.
app/golden_dataset.py   Synthetic demo data.
app/seed.py      Loads golden dataset into the configured database.
```

## Why engines never import SQLAlchemy or FastAPI

If `replay_engine.py` could open a DB session, "the core does not depend on external
state" would be a documentation claim, not a structural guarantee. Instead, every
engine function takes a `DecisionContext` (or a `Decision`) as a plain in-memory value
and returns a plain in-memory result. The API layer and repository are the only code
that touches persistence. This is also why the engines have a dedicated unit test
suite that runs with zero database, zero network, in under a second.

## Persistence: JSON columns for the context, real columns for everything queried

`DecisionRecord.context_json` stores the full `DecisionContext` (evidence, tools,
retrievals, model/policy snapshot) as one JSON blob. This is deliberate:

- The context is always read and written as one atomic unit (it's a frozen snapshot;
  there is no use case for partially updating just one evidence item in place).
- Postgres JSONB still supports querying into it if that's ever needed.
- Everything that IS queried directly by column (`decision_id`, `system`, `timestamp`,
  `risk_score`, `decision`, `context_hash`) gets a first-class indexed column.

This trades some referential integrity (an `Evidence.evidence_id` inside the JSON isn't
a DB-level foreign key) for a schema that matches the actual access pattern. If a
future version needs to query "give me every decision that used evidence source
`identity-service`" efficiently at scale, that's the trigger to normalize evidence into
its own table -- not before.

## Request flow for the killer feature (counterfactual)

```
POST /decisions/{id}/counterfactual
  -> repo.get_decision()               load + deserialize the frozen DecisionContext
  -> mutation_engine.apply_mutations() build a NEW context, original untouched
  -> replay_engine.replay() x2         once on original context, once on mutated
  -> diff_engine.diff_decision()       structural diff + score delta
  -> causal_engine.analyze()           precise causal-status wording
  -> repo.save_mutation/counterfactual persist for audit trail
  -> return CounterfactualOut
```

Nothing here is short-circuited for the demo -- `DEC-001`'s BLOCK->ALLOW flip is
produced by this exact code path, not a canned response (see `tests/test_api_integration.py::test_counterfactual_killer_demo_via_api`).
