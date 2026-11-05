# Merlin HUD Runtime Integration v1

## Runtime mount

The current HTTP entrypoint is `python/merlin/app.py`. It serves the neural HUD at
`/hud` and mounts the read-only HUD JSON routes in the same loopback server:

- `GET /api/hud/activity`
- `GET /api/hud/graph`
- `GET /api/hud/node?node_id=...`

The mount is performed by `make_handler(store, hud_runtime)`, which adapts the
WSGI HUD application to the existing `BaseHTTPRequestHandler`. Host routes
remain owned by the existing HTTP application.

The current HUD file `ui/merlin-hud/index.html` is now the primary static file
served at `/hud`; `web/merlin_hud.html` remains a legacy fallback.

## Canonical store binding

The server binds the HUD only when all required paths are explicitly configured
and their canonical database files already exist:

- `MERLIN_REGISTRY_ROOT`: directory containing `merlin.sqlite3` and the
  registry's content-addressed `blobs/sha256` store.
- `MERLIN_GRAPH_DB_PATH`: canonical knowledge graph SQLite database.
- `MERLIN_OUTBOX_DB_PATH`: canonical event outbox SQLite database.
- `MERLIN_HYPOTHESES_DB_PATH`: optional hypothesis ledger SQLite database.

No empty replacement stores are silently created when these settings are absent
or point to missing database files. In that case HUD endpoints return 503 and
the browser retains its clearly labelled demonstration mode.

The composition root is `merlin.hud_runtime.build_hud_runtime`. It receives the
same store instances used by Merlin services, constructs `MerlinReadAPI`, and
injects it into `HudActivityWSGI`. The graph endpoint returns the canonical
snapshot and the node endpoint returns the canonical node, typed neighbors,
artifact digest metadata, and a typed workspace descriptor.

The server starts a bounded background `HudEventPump` when the canonical outbox
is connected. The HTTP GET endpoints do not claim or acknowledge outbox events;
event delivery and acknowledgement happen in that separate consumer loop.

## Typed research and engineering workspaces

Graph node types now include:

- Mathematics: `equation`, `equation_atlas`
- Formal proof: `theorem`, `proof_receipt`
- CAD: `cad_model`, `freecad_model`, `freecad_assembly`
- Electrical engineering: `electrical_net`
- Experiments: `experiment`, `simulation`, `simulation_result`

`merlin.hud_objects.render_descriptor` maps canonical node payloads into
workspace-specific view models. Equation payloads preserve LaTeX, coordinate
systems, variables and transformations. Lean payloads preserve declaration,
assumptions, axiom dependencies and receipt metadata. CAD payloads preserve
document/object/assembly/geometry and artifact references. Electrical payloads
preserve components, nets and connections. Simulation payloads preserve engine,
parameters, seed, samples, series, metrics and units.

These are typed read-only data contracts. A graph node or artifact digest does
not prove mathematical correctness, CAD manufacturability, electrical safety,
or simulation validity. The browser currently previews these payloads; full
native FreeCAD rendering, interactive netlist editing, and plotted simulation
series still require their dedicated renderer/runtime adapters.

## Agent event lifecycle

All service events use the versioned `merlin-telemetry/1` contract and the
durable outbox topic family `merlin.telemetry.<kind>`. Service-bound publishers
are created with `agent_event_sink(outbox, service)`; the source identity is
fixed at construction and cannot be changed by each event payload.

Connected event producers:

- Hermes dispatch: queued task and awaiting-worker status.
- MCFC admission: validated lease status and **reserved** CPU/memory/time/compute
  budget. These are reservations, not measured consumption.
- Avrea adapter: accepted runner/job assignment, completion status, collected
  artifact references, and observed resource metrics when the injected runner
  transport returns a `resource_metrics` object.
- CACE adapter: proof check, independent verification result, verifier status,
  and a receipt digest reference after receipt validation and registry storage.

Hermes execution-start/progress/completion events must be emitted by the actual
Hermes worker when it is connected. MCFC consumption metrics must come from the
actual scheduler/runner; the admission layer only reports reservations. Missing
measurements remain absent rather than being inferred.

The HUD's green verification state is emitted only for a CACE-sourced
`verification.completed` event marked independent and carrying an evidence
reference. Demonstration events are explicitly marked as simulation and cannot
create that state.

## Authority and operational boundaries

- The HUD and workspace descriptors are read-only.
- The event pump acknowledges telemetry only after successful projection.
- The outbox remains at-least-once; event IDs provide idempotent projection.
- No dispatch occurs merely because the HUD is open.
- Avrea dispatch still requires explicit approval and a validated MCFC lease.
- CACE verification does not promote hypotheses or expand execution authority.
- The server remains loopback-bound by default.
- No deployment, merge, paid service, or external runner activation is performed
  by this integration.
