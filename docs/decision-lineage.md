# Decision Lineage

`GET /decisions/{id}/lineage` builds a graph, not a list:

- `INPUT` -> `RETRIEVAL` (edge: `USED_BY`) -> `EVIDENCE` (edge: `DERIVED_FROM` if the
  evidence came via a retrieval, `USED_BY` if directly attached)
- `EVIDENCE` -> `MODEL` (edge: `USED_BY`)
- `MODEL` -> `POLICY` (edge: `EVALUATED_BY`)
- `POLICY` -> `CONTROL` (edge: `GOVERNED_BY`) for each required control
- `POLICY` -> `DECISION` (edge: `RESULTED_IN`)

Every node carries its own id and is independently addressable (you can fetch full
evidence detail for any `EVIDENCE` node via `GET /decisions/{id}` and matching the
`evidence_id`). The graph is generated fresh from the stored `DecisionContext` on every
request -- it is not a separately maintained, potentially-stale copy.
