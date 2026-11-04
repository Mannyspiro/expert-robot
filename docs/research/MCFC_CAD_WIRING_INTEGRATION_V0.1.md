# MCFC–CAD–Wiring integration plan (Merlin / CACE)

## Purpose

Connect one typed engineering object across mechanical CAD, electrical connectivity,
wire-harness geometry, simulation, and evidence review without pretending that a
coordinate conversion or a visually plausible model is an engineering approval.

**MCFC** in this repository means **Multi-Coordinate-Frame Contract**: a set of
explicit, typed relationships between reference frames, not an additional physical
dimension and not a free-form mixing of coordinates.

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
