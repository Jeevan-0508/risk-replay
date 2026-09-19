# Incident Blast-Radius Forensics

## What it is

`backend/app/engines/incident_engine.py` computes the real, replay-derived
impact of an incident across every decision grouped under it. An incident
(`IncidentRecord`) can optionally be tagged with a suspected
`affected_evidence_kind` — the evidence dimension an investigator believes
was compromised (e.g. an identity-verification signal that was later found
to be unreliable). When that tag is present, the engine runs a real
per-decision counterfactual: remove the matching evidence item, replay, and
record whether the outcome actually flips.

Endpoint: `GET /incidents/{incident_id}/blast-radius`.

## What every number in the response actually measures

- `replayable_count` / `partially_replayable_count` / `non_replayable_count`
  — the real `replay_engine` status for every decision in the incident,
  tallied the same way `sweep_engine` does for a single decision.
- `affected_policies` / `affected_models` / `affected_evidence_sources` /
  `affected_controls` — the real sets pulled from each decision's stored
  context and control evaluations. Always populated, whether or not a
  suspected evidence kind was supplied.
- `decisions_with_dependency` — how many decisions actually contain an
  evidence item of the tagged kind (found by scanning `context.evidence`,
  not assumed).
- `decisions_changed` / `decisions_unchanged` — of those, how many flip
  outcome when a real `Mutation(REMOVE_EVIDENCE)` counterfactual is run
  through `counterfactual_engine.run_counterfactual`. This is the same
  engine the single-decision counterfactual screen uses; nothing here is a
  separate, unverified code path.
- `decision_impacts` — per-decision detail: which evidence item, the
  baseline outcome, the counterfactual outcome, and whether it changed.

## The "common replay dependency" wording rule

The response's `common_replay_dependency.note` field always reads:

> "Common replay dependency: a shared variable whose removal changes these
> decisions' outcomes under replay. This is not asserted as the real-world
> root cause."

This is deliberate. A shared evidence kind whose removal flips several
decisions under replay is a fact about the deterministic replay model, not
proof that the real-world incident was caused by that variable. The word
"root cause" never appears anywhere else in this response — only in that
disclaimer, by name, so nobody mistakes the label for a causal claim.

## Honest no-op path

If an incident has no `affected_evidence_kind` set, the endpoint still
returns real replayability and affected-scope data, but
`decisions_with_dependency`, `decisions_changed`, `decisions_unchanged` all
stay `0` and `common_replay_dependency` stays `null` — there is no
per-decision test to run, so nothing is fabricated to fill the field.

## Known gap fixed this phase

Before this phase, the blast-radius endpoint called the older
`risk_engine.blast_radius(decisions, [])` with a hardcoded empty
`changed_replays` list — so `decision_changes` / `human_review_changes` /
`high_risk_changes` were always `0`, regardless of the actual incident.
That endpoint now delegates entirely to `incident_engine.analyze_blast_radius`,
which computes every number from a real per-decision replay and
counterfactual.

## Known gaps, disclosed

- No dedicated Incident Console frontend screen exists yet. This phase is
  backend-only: a real API, tested and live-verified, with no UI built on
  top of it.
- The static (GitHub Pages) demo bundle has not been extended with incident
  data or a client-side port of this engine.
