# Hermes worker and engineering workspaces v1

## Hermes execution lifecycle

`python/merlin/hermes_worker.py` provides the worker-side consumer for
`merlin.hermes.task`. It claims only that topic; it cannot consume HUD
telemetry, Avrea dispatch messages, or unrelated outbox traffic.

The worker performs the following sequence:

1. Claim a task using the durable outbox lease.
2. Validate the versioned research-task envelope, required resource limits and
   the explicit `bounded_execution_only` authority declaration.
3. Resolve a stage-specific handler from the injected handler registry.
4. Revalidate the operator approval reference and MCFC lease immediately
   before invoking the handler.
5. Emit Hermes agent status, task progress, and tool-start/tool-completion
   events through the common source-bound telemetry outbox.
6. Collect the handler's result and evidence references into a
   `merlin-hermes-task-result/1` receipt.
7. Acknowledge the task with that receipt, or apply bounded retry and eventual
   quarantine on handler failure.

Admission failures are recorded as rejected results and acknowledged without
calling the handler. The worker never grants hypothesis-promotion authority
and never dispatches Avrea by itself.

### Runtime injection contract

A service process must construct the worker with the canonical outbox, the
actual stage handlers and the same approval/lease validators used by Merlin:

```python
worker = HermesWorker(
    canonical_outbox,
    handlers=registered_stage_handlers,
    approval_validator=approval_service.validate_task,
    lease_validator=mcfc_lease_service.validate_budget,
)
worker.run_forever(stop_event)
```

The example names above are interfaces, not existing connected provider
instances. This repository change supplies the worker engine and lifecycle;
it does not invent a provider handler or silently start one in the API server.
The deployment must register actual stage handlers and supervise this worker
as a separate process/service.

Every handler receives a stable `idempotency_key`, the declared resource
budget and a wall-time deadline in `TaskExecutionContext`. Handlers must use
that idempotency key for any side effect, check the deadline while progressing,
and enforce the resource budget at the actual execution boundary. The worker
rejects a task whose declared wall-time budget exceeds its configured outbox
lease duration. A handler that blocks without checking its deadline still
requires an external process/container supervisor for hard termination.

The outbox provides at-least-once delivery, not magical exactly-once execution.
A crash after a handler side effect but before acknowledgement can cause a
retry. Stage handlers must therefore be idempotent and return content-addressed
evidence references only after storing and verifying their artifacts.

## Engineering workspace renderers

The neural HUD now renders typed engineering objects in a workspace panel:

- **FreeCAD/CAD:** bounded part-box geometry is projected into an interactive
  3D-style SVG viewport. Drag rotates the view, wheel zooms and reset restores
  the default projection. The renderer uses supplied millimetre dimensions and
  positions; it does not invent geometry or launch FreeCAD.
- **Electrical:** component identities and net endpoint references are rendered
  as a selectable connectivity diagram. The diagram is a wiring visualization,
  not ERC, SPICE analysis, electrical safety certification or sign-off.
- **Simulation:** numeric series are plotted from supplied samples. Series can
  be isolated, and axes are scaled from the recorded data. No measurements are
  inferred when samples are absent.

Renderer inputs are bounded before display (CAD parts and electrical components,
net records, simulation series and sample counts). All views remain read-only
and preserve the canonical node/artifact provenance shown by the HUD.

These are native browser renderers for the typed payload contracts, not a
replacement for FreeCAD's full modelling kernel, an electrical solver or a
simulation engine. The next integration step is to have the actual domain
engines publish these typed objects and their content-addressed result files
into the canonical registry and graph.

## Validation and operational state

Tests added:

- `tests/test_hermes_worker.py`: handler execution, progress/tool lifecycle,
  approval and MCFC lease revalidation, retry/quarantine and topic isolation.
- `tests/test_hud_objects.py`: typed CAD, electrical and simulation workspace
  descriptor preservation.

The tests have been added but must be run locally or in a deliberately selected
CI run before this branch is considered verified. The worker is not started by
the HTTP server; no actual handler registry, live Hermes process, FreeCAD
installation, electrical solver, or simulation engine is claimed to be
connected by this change.

Capability grows, authority never expands.
