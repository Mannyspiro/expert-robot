# Merlin HUD Activity Contract v1

Status: implemented projection and WSGI adapter; integration with the main runtime remains a mount step.

## Visual hierarchy

1. **Upper activity HUD** — a thin, animated visualization of observable system activity: task phase, active agents, tool calls, event stream, measured resources, proof/verification events and evidence counts.
2. **Adaptive research canvas** — below the HUD, changes its visualization according to the current stage: intake, hypothesis graph, representation transform, experiment, counterexample search, formalization/proof DAG, verification or artifact lineage. Engineering tasks can select assembly or wiring visualizations when those adapters are connected.
3. **Bottom chat** — persistent text composer and voice-input affordance. Chat and voice must eventually submit through the same authenticated task API.

The central canvas is not a permanently fixed chart. Its view is selected by the active task and stage.

## Observable activity, not private reasoning

The HUD does not expose hidden chain-of-thought. It renders event records that can be independently inspected:
- task.started, task.progress, task.completed
- research.stage, hypothesis.updated
- model.inference
- agent.status, agent.tool.started, agent.tool.completed
- experiment.completed, proof.checked, verification.completed
- resource.sample, artifact.registered, outbox.acknowledged
- operator.action, system.error

The animation layer may interpolate movement between events for readability. Interpolated motion is presentation only; event timestamps, values and evidence references remain authoritative. Simulated/demo mode must be visibly labelled and must never be counted as runtime evidence.

## Implemented modules

- python/merlin/telemetry.py: one normalized telemetry event contract and event-kind vocabulary.
- python/merlin/event_outbox.py: durable event delivery with idempotency, topic-filtered claims, leases and acknowledgements.
- python/merlin/hud_activity.py: bounded event projection and HudOutboxConsumer.
- python/merlin/hud_http.py: read-only WSGI endpoint.
- ui/merlin-hud/index.html: minimal full-screen shell with upper event visualization, adaptive stage canvas and bottom chat/voice controls.
- tests/test_hud_activity.py, tests/test_hud_http.py: projection and endpoint tests.

## HTTP contract

Mount HudActivityWSGI(projector, consumer) at GET /api/hud/activity on the local Merlin runtime. It returns JSON with schema merlin-hud-activity/1:
- active_run_id, phase, phase_index, phases
- agents, resources, timeline, evidence_refs
- event_count, latest_event_id
- visualization_policy

The adapter is read-only from the client perspective. When configured with HudOutboxConsumer, it drains only merlin.telemetry.* events into the projector before returning the projection. Bind the runtime to loopback by default; production exposure requires the host runtime's authentication and authorization middleware. The static HUD polls this endpoint; it labels fallback animation as DEMO.

## Canonical ownership boundaries

| Data | Canonical owner | Other modules' role |
|---|---|---|
| Projects and content-addressed artifacts | MerlinRegistry | Query facade and graph projections |
| Hypotheses and hypothesis evidence | HypothesisLedger | Registry query facade; graph projection |
| Typed graph nodes/edges | MerlinKnowledgeGraph | Derived views, not competing stores |
| Durable events and delivery state | MerlinEventOutbox | Hermes and HUD are consumers |
| Event schema and normalization | telemetry.py | Producers emit; consumers project |
| Lean attempts and tactic observations | ProofObservatory | Hypothesis ledger receives qualified proof evidence |
| Equation-atlas definitions/experiments | equation_atlas | Receipts link to hypotheses and graph |
| Engineering project revisions | EngineeringProjectStore | CAD/wiring views and graph bridge |
| Bounded execution grants | MCFC LeaseBook | Runner adapters consume grants; no promotion authority |

MerlinRegistry.claims remains a legacy/general claim metadata table. New mathematical hypothesis lifecycle records belong in HypothesisLedger; do not dual-write the same hypothesis to both stores. The Knowledge Graph is a provenance-linked projection and must not be treated as a second authoritative hypothesis store.

## Current integration boundaries

- HermesOutboxConsumer is a generic injected-handler boundary. It now claims only the configured Hermes task topics and records result acknowledgements; the actual Hermes Agent runtime handler still has to be wired to it.
- MCFC LeaseBook is an in-process reference implementation. Its event sink can use telemetry_outbox_sink; persistent leases and measured runner capacity still need implementation.
- CapacitySnapshot.from_probe_document accepts an Avrea probe artifact, but no live Avrea dispatch is claimed until a runner and approval flow are available.
- CACE proof receipt validation is structurally useful but does not independently authenticate GitHub workflow identity. Independent GitHub and Lean verification remains a separate integration.
- engineering_ir.py, EngineeringProjectStore, coordinate representation graph views and observatory_graph_bridge.py provide the existing CAD/wiring-to-evidence foundation. FreeCAD installation and live GUI integration are not claimed.
- The static chat and voice controls are interface affordances; they are not a working conversational endpoint until the authenticated task/chat API is mounted.

## Acceptance tests

- Duplicate event IDs do not duplicate HUD timeline entries.
- The HUD consumes only telemetry topics and acknowledges them after successful projection.
- A failed projection is retried and not falsely marked acknowledged.
- Event history is bounded.
- Upper activity state is derived from actual events; demo state is labelled separately.
- The adaptive canvas switches by research phase.
- POST requests to the activity endpoint are rejected.
- No private reasoning text is exposed by the projection.