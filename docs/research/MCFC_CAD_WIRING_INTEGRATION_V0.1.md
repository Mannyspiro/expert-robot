# MCFC Virtual Fabric × CAD/Wiring integration plan (Merlin / CACE)

## MCFC responsibility and CAD workload contract

MCFC owns the execution envelope, not the CAD truth:
- resource types: CPU cores, memory bytes, GPU count and GPU memory (unknown remains unknown);
- workload requirements: task type, requested resources, maximum wall time, compute budget, and required capabilities;
- scheduling: bounded concurrency and deterministic admission decisions;
- leases: expiring, revocable execution grants with explicit resource reservations;
- telemetry: measured runtime resource samples, kept separate from synthetic simulation;
- policy: no worker may promote its own result or expand authority.

A CAD/wiring job is a typed workload submitted to MCFC. For example,
`cad.wire_route_proposal` is CPU-only unless a later measured implementation
proves a GPU path is useful. Its request must state resource estimates and
time/budget limits; estimates are not hardware facts. MCFC grants a lease only
when the current capacity snapshot is known and sufficient. If GPU capacity is
unknown, a GPU-required workload is held or rejected rather than assigned an
invented device.

Merlin consumes the lease to run the CAD/wiring workload. CACE independently
checks the resulting project revision, geometry, netlist, route artifact,
resource/telemetry receipt, and declared verification tests. A successful lease
only authorizes bounded execution; it does not approve the engineering result.

## Purpose

Connect one typed engineering object across mechanical CAD, electrical connectivity,
wire-harness geometry, simulation, and evidence review without pretending that a
coordinate conversion or a visually plausible model is an engineering approval.

**MCFC** is Merlin's **virtual compute fabric**. It manages typed CPU, memory and
GPU resources, compute budgets, workload scheduling, expiring execution leases,
and resource telemetry. It is not the coordinate-frame system.

Coordinate-frame semantics belong to Merlin's XMG multi-frame contract: typed
frames, rigid transforms, units, projections, embeddings, and declared invariants.
Do not conflate a compute-resource lease with a geometric transform.

## Reframing the problem as exact analogues

| Informal engineering question | Exact mathematical / computational analogue | Merlin implementation target |
|---|---|---|
| Where is this pin in the assembled device? | Composition of rigid transforms in SE(3), followed by a point action | `coordinate_frames.py`, `physical_connectivity.py` |
| How does the same device appear in board, enclosure, sensor, and harness coordinates? | One canonical object with typed frame maps and declared units | MCFC frame graph and transform receipts |
| Are two parts occupying the same space? | Broad-phase collision detection using transformed AABBs, followed by exact solid geometry later | `cad_assembly.py`; AABB is warning-only |
| How can a net be represented in 3D? | A graph edge / hyperedge embedded as a polyline in a metric space | `engineering_ir.Net`, `wire_routing.py` |
| Can a plausible path be proposed around components? | Deterministic orthogonal path search with conservative keep-out boxes | `wire_routing.py` candidate planner |
| Is the wire actually suitable? | Electrical, thermal, mechanical, regulatory and manufacturing qualification | Explicitly out of scope until source data and independent tools exist |
| Does a simulation support the design? | A declared model with units, boundary conditions, solver assumptions, and residuals | Equation Atlas + simulation receipts |
| Can CACE promote the result? | Evidence-gated state transition with independent checks and rollback | CACE capability/evidence bridge; no authority expansion |

## Canonical object and frames

Treat the assembly as a canonical typed object (O), with frame graph:

- `world`: declared assembly datum;
- `enclosure`: mechanical enclosure datum;
- `board`: PCB datum;
- `component/<ref>`: component-local datum;
- `pin/<ref>.<number>`: pin-local geometry;
- `harness`: wiring route-planning datum;
- `sensor/<id>`: measured or instrument datum;
- `thermal`: optional analysis frame, with explicit mapping and assumptions.

Each frame edge stores parent, child, rigid transform, units, source, revision,
uncertainty/tolerance, and evidence status. Rigid transforms preserve Euclidean
distances and angles; projection into a drawing or 2D PCB view is lossy and must
be marked as such. A 3D rendering is not evidence of correct dimensions.

## Current implementation bridge

1. `EngineeringProject` is the typed source for parts, pins, nets, dimensions,
   voltage/current declarations, and units.
2. `CADAssembly` and `CoordinateFrame` place components in nested frames.
3. `physical_netlist()` resolves pin coordinates into the assembly frame.
4. `route_physical_netlist()` proposes deterministic orthogonal polylines around
   conservative component AABBs. Multi-terminal nets currently use a deterministic
   star rooted at the lexicographically first endpoint.
5. Simulation and evidence receipts must consume the same project revision and
   geometry hash; they must not silently use stale exports.

## Wiring route proposal semantics

The new route planner emits one of:

- `candidate_geometry_not_manufacturing_qualified`
- `unroutable_missing_endpoint_geometry`
- `blocked_no_candidate_path`
- `not_routable_insufficient_endpoints`

A candidate route includes ordered 3D points, segment count, length, method,
and the assumed geometric clearance. Obstacles are transformed component AABBs.
An elevated Z overpass is a fallback candidate; it is not an instruction to route
a real cable above an enclosure or board.

## Engineering qualification gates (future work)

Before any generated geometry is used for fabrication or energized hardware,
independent domain-specific tools and qualified review must establish:

- authoritative component and connector datasheets, pin numbering, tolerances;
- wire type, conductor size, insulation, temperature rating, ampacity and derating;
- voltage-domain separation, creepage/clearance and applicable standards;
- impedance, return paths, signal integrity, EMC/EMI and grounding strategy;
- thermal dissipation, fault behavior, protection, fusing and current limits;
- minimum bend radius, strain relief, abrasion, service loops and assembly sequence;
- exact solid collision checks, tolerance stack-up and manufacturability;
- simulation/measurement correlation, uncertainty bounds and revision traceability.

Missing data is an explicit blocker, never filled by a guessed default.

## CACE evidence and authority model

CACE should treat each proposed route as an artifact requiring a receipt containing:
project and assembly revision hashes, frame-graph hash, input netlist hash,
router version, clearance assumption, obstacle geometry hash, output route hash,
test results, and qualification status.

Suggested states:

`DRAFT → STRUCTURALLY_VALIDATED → GEOMETRY_PROPOSED → INDEPENDENTLY_REVIEWED → QUALIFIED`

Only a human-approved, evidence-complete transition can promote a design. The
router cannot approve itself, and a successful CI run proves only the declared
software tests. **Capability grows, authority never expands.**

## Avrea CI scope

Add a deterministic unit-test stage for route generation, obstruction handling,
missing geometry, multi-terminal topology, invalid clearance, and the explicit
non-qualification status. Publish route examples only as synthetic reproducibility
artifacts. No empirical or fabrication qualification is claimed.

## CACE route-evidence bridge

`python/merlin/route_evidence.py` now creates a content-addressed evidence receipt
binding the canonical engineering-project hash, assembly hash, frame-graph hash,
route-output hash, router version, and exact source commit. The receipt labels its
scope as synthetic geometry proposal, keeps qualification status at
`not_qualified`, and hard-codes `promotion_authority: false`.

Before adding a receipt to the Merlin hypothesis ledger, the CACE-facing adapter
recomputes every bound hash from the supplied project, assembly, and route output.
A mismatch rejects ingestion. Successful ingestion adds an `experiment` evidence
record but leaves the hypothesis status unchanged. CI tests verify the hashes,
tamper rejection, authority boundary, and no-auto-promotion behavior.

The receipt is a local provenance object. It does not independently authenticate
a GitHub workflow or replace the separate Avrea run receipt; the CI run must be
checked against the exact commit SHA.

## Current repository integration points

- `python/merlin/cpu_fabric/leases.py`: typed MCFC workload requirements, measured capacity snapshots, resource admission, expiring/revocable leases, and runtime telemetry.
- `python/merlin/cpu_fabric/leases.py::cad_wire_route_request`: creates a CPU-only CAD routing workload. Memory, wall-time and compute-budget estimates are explicit caller inputs.
- `python/merlin/wire_routing.py`: deterministic candidate geometry generation under an MCFC lease.
- `python/merlin/wiring_exports.py`: logical graph, connection schedule and schematic manifest exports, all marked as non-release artifacts.
- `python/merlin/wire_qualification.py`: evidence-gated electrical, thermal and manufacturing screening. Missing authoritative inputs block release; the report never calls the design safe or self-certifies it.
- `python/merlin/route_evidence.py`: content-addressed CACE receipt that binds the completed MCFC lease, capacity evidence hash, engineering project, assembly/frame graph, route output and source revision.
- `python/merlin/telemetry.py`: source-labelled runtime telemetry; MCFC lease events are recorded as runtime resource samples, not simulation data.

The current `LeaseBook` is an in-process reference implementation, not yet a
durable distributed scheduler. Live hardware capacity, lease persistence across
restarts, worker heartbeats, preemption, fairness, native EDA export, SPICE
simulation, and independent electrical sign-off remain separate completion gates.

## MCFC queue/admission boundary

`WorkloadScheduler` now orders queued CAD jobs by descending declared priority
and FIFO for ties, then asks `LeaseBook` to reserve measured CPU/memory/GPU and
compute-budget capacity. A request that does not currently fit remains queued;
smaller eligible work may proceed. This is a deterministic first-fit admission
policy, not a production fairness guarantee or a worker executor. The scheduler
does not spawn processes, preempt active work, or persist its queue across restarts.
