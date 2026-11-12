# Merlin telemetry contract and simulation lab

## Telemetry boundary

The merlin.telemetry.normalize_event function validates caller-supplied events
against merlin-telemetry/1. Sources remain distinct:

- runtime: measurements emitted by an actual orchestrator/runtime adapter.
- simulation: synthetic world measurements.
- model_output: model-produced text or structured output, not private thoughts.
- verifier: results from an identified verifier.
- operator: human control actions.

Events carry run/task identifiers, timestamps, typed payload metadata, optional
evidence references, model identity, duration, CPU percentage and memory bytes.
Unknown sources, unknown event kinds, non-finite metrics, and invalid resource
values are rejected. The normalizer does not collect machine metrics itself.
Adapters must not relabel simulation data as runtime data.

## Deterministic simulation lab

The simulation_lab module adds three bounded scenario presets:
steady_research, uncertainty_recovery, and resource_pressure.
run_scenario executes a fixed action log; compare_scenarios evaluates each
scenario against the same seed list; replay_actions deterministically
reconstructs a run from its action log.

The current world is deterministic. Seeds are recorded for reproducibility and
paired comparison interfaces, but do not yet randomize the world. These results
are useful for checking state transitions and HUD behavior, not for statistical
significance or claims that one research strategy is better. The next upgrade
should introduce a documented seeded stochastic world, paired workload
generation, confidence intervals, and held-out seeds.

## Next integration sequence

1. Add runtime adapters from actual orchestrator, verifier, and local-model boundaries.
2. Persist normalized event envelopes and simulation action logs in SQLite.
3. Add multiscale graph visualization from real task/evidence/dependency IDs.
4. Connect council output as model_output events and display stance, evidence,
   disagreement, and revisions.
5. Improve catalog loading with streaming hash verification and immutable
   file-descriptor snapshots; add signed provenance before accepting modules.
6. Evaluate baseline, specialist, fixed alternation, adaptive selection, and
   fallback with paired workloads and independent verification.

Nothing here authorizes automatic promotion, repository mutation, deployment,
or expansion of agent authority. Capability grows, authority never expands.

## Durable replay and graph

Simulation actions are appended to the existing SQLite event ledger. On server
startup, the simulation state is reconstructed by replaying those actions in
order. GET /api/sim/replay returns the action log and reconstructed state.
This is bounded to the latest 10,000 persisted actions; deployments with longer
histories should introduce snapshots/checkpoints before increasing the limit.

GET /api/telemetry/graph projects actual recorded identifiers into run, task,
event and evidence levels. It draws only explicit containment and evidence
reference edges; it does not infer causal relationships. The HUD displays live
counts from this endpoint.

Council inference emits metadata-only model_output telemetry, including model
label, transcript digest and response counts; the transcript itself remains
separate from the graph projection. RSI qualification emits verifier-labeled
outcome metadata. Neither event grants authority.
