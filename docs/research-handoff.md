# SWARM research handoff

The local **Research Capture Review** screen accepts `swarm-research-capture.v1` JSON from RISK//SWARM. The file is parsed and displayed in browser memory. It is not POSTed to the API, written to the database, added to a `DecisionContext`, or treated as a deterministic re-execution of the providers.

The strict v1 wrapper is `contracts/risk-replay-research-handoff.v1.schema.json`. It pins the nested SWARM capture schema to one immutable Risk-Swarm commit. The exported wrapper always says `review_state: unreviewed` and `replay_status: not_replayed`; this UI has no control that can promote either value.

External source records and Fraud Watch context render in separate panels. The external list accepts only records marked `external_source_content` / `retrieved_source_record`; the optional Fraud Watch object must remain `synthetic_simulation`, `hypothesis_context_only`, and `unverified_export`. Internal SWARM knowledge text, derived/model conclusions, and knowledge-promotion outputs are excluded by the capture contract.

The **Download unreviewed MESH handoff** action creates a portable wrapper for manual transfer. It adds only the local receipt time and fixed unreviewed/not-replayed states. Neither the wrapper nor a text fingerprint proves authenticity, source independence, factual truth, or claim entailment. Promotion to shared knowledge is outside this handoff and requires a separately reviewed process.
