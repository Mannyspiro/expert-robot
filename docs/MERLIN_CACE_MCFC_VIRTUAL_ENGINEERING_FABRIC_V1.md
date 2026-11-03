# Merlin / CACE / MCFC — Unified Virtual Engineering Fabric v1

Status: living implementation specification, derived from supplied project artifacts and observed prototypes.
Invariant: capability grows; authority never expands.

## Observation-derived requirements

| Observation | Derived requirement | Confidence |
|---|---|---|
| Runtime registry distinguishes unavailable/configured/unqualified/qualified. | Derive state from live probes, exact model identity and matching receipt; configuration is not qualification. | High |
| Async gateway bounds concurrency, deadlines, chunk and total bytes. | Preserve limits and propagate cancellation through transports. | High |
| Qualification receipts bind revision, artifact, held-out tasks/seeds and privacy review. | Routing binds exact identity and held-out evidence; never trust UI/env booleans. | High |
| CACE envelope hashes evidence but verifier boolean is an external claim. | Recompute hashes and validate verifier provenance; boolean alone is insufficient. | High |
| Runner inventory exists but live MCFC integration is incomplete. | Separate read-only discovery, reservation, leases and execution adapters. | Medium |
| MVP 0.2 has local persistence, provider chat and Kokoro; CAD, media and CACE qualification are incomplete. | Preserve local-first operation and expose unavailable states honestly. | High |
| CAD prototype exposes substrate, dielectric, trace, nets, vias, mesh, guard ring and 50-ohm suggestion. | Promote controls to typed inputs with units, assumptions, constraints and provenance. | High |
| CAD drafting plates are session-only. | Persist revisions and render artifacts by digest and lineage. | High |
| Existing UI distinguishes REAL and SIM requirements. | Preserve REAL/SIM/HYPOTHESIS labels and observation-to-test lineage. | High |

## Unified job contract
Every job carries ID, type, schema, project/revision, input hashes, requested resources, budget, deadline, idempotency key, status, lease, telemetry refs, output hashes, evidence refs and approval state. Scheduling is not execution authority. authority_expanded remains false.

## Merlin runtime
Probe real provider health and identity. States: unavailable, configured, unqualified, qualified. Qualification binds provider/model/revision, artifact digest, runtime build, quantization/context, held-out manifest, evaluator revision and privacy review digest. Secrets remain server-side.

## MCFC virtual fabric
Resource vector: CPU millis, memory MB, GPU units. Discover stable IDs, capacities, labels, online state, observation time and source. Workloads specify resource request, labels, priority, runtime bound and input hashes. Enforce per-resource and global budgets; idempotency; expiring leases; expiry reclamation; lifecycle telemetry. First adapter is deterministic/in-memory. Runner/Avrea discovery starts read-only. Scheduler never executes arbitrary code.

## CACE evidence bridge
Evidence types: source, test, proof, benchmark, qualification, simulation, CAD validation, review and media. Bind repository, immutable revision, artifact path/hash, evidence hash, producer, verifier and method. Consumer recomputes hashes and checks verifier trust policy. States: observed, ingested, hash_valid, independently_verified, rejected, superseded. Hash integrity is not scientific truth.

## Measured routing and virtual laboratory
Use identical held-out manifests, randomized order, exact model/runtime/artifact identity and paired deltas. Measure quality, latency, throughput, peak memory, failure rate and compute cost; report uncertainty. Held-out data is not tuning data. Route recommendations remain advisory. Unified jobs include simulation, research, tests, Lean proofs, numerical experiments, CAD solves, image and video renders. Record source revision, environment, solver, seeds, units, assumptions, parameters, lease and output hashes. SIM never silently becomes REAL.

## CAD and wiring workbench
Typed model includes geometry (units, coordinate frames, dimensions, layers, clearances, tolerances), electrical topology (components, pins, nets, wires, vias, trace widths, copper, dielectric stackup, voltage/current/temperature ratings), constraints (impedance, spacing, bend radius, thermal, manufacturability), source observations and derived requirements.

Never invent missing voltage/current ratings, conductor material, safety class, dielectric properties, clearances or tolerances. Missing safety-critical inputs block release-ready status.

Inductive loop: ingest observations; extract candidate entities, measurements and relations with uncertainty; propose requirements with provenance/confidence; detect conflicts and missing units; ask only decision-critical questions; generate editable geometry/netlist; run deterministic geometry/connectivity/ERC/DRC/domain checks; compare predictions with observations; update candidate requirements with residuals and revision history; require human approval for baseline and physical release.

Prototype ranges observed: length 40–160 mm, width 24–120 mm, relative permittivity 2–12, substrate 0.2–3.2 mm, trace 0.1–6 mm, nets 1–12, vias 0–16, mesh U 4–64, V 4–80. These are UI ranges, not certified limits. Solver validity, frequency, stackup, reference plane, copper roughness, solder mask and edge effects must be explicit.

### CAD image/video generation
Provider-neutral image/video adapters accept CAD revision plus render brief (camera/view, scale, material, lighting, annotations, duration, frame rate). Outputs are visualization artifacts linked to CAD revision and prompt/config hashes. They never replace editable geometry, netlists, manufacturing drawings, DRC/ERC/LVS or engineering sign-off. If provider unavailable, show unavailable. Confidential design egress requires explicit approval. Each render links to exact CAD revision.

## Unified interface
Panels: Runtime, Fabric, Jobs, Evidence, Routing, Lab, CAD, Media, Inductive Requirements. Show observed/cached/simulated/inferred/unavailable/stale state with timestamp and source. Expose budgets, leases, progress, output hashes, provenance, assumptions and approval gates.

## Acceptance criteria
- Live provider state cannot claim qualified without exact matching receipt.
- Fabric enforces budgets, labels, idempotency and expiry.
- Job telemetry links input/output artifacts by digest.
- CACE independently recomputes hashes and validates verifier attestation.
- Routing uses disjoint held-out data and uncertainty; no automatic promotion.
- Lab runs are reproducible from revision, seeds, parameters and environment.
- CAD geometry/netlists remain editable independent of generated media.
- CAD validation records units, assumptions, solver version and unresolved constraints.
- Image/video renders bind to CAD revision and cannot mark design validated.
- Requirement revisions preserve observation lineage and approval history.
- No physical actuation, deployment, external data egress or authority expansion without explicit approval.

## Build sequence
A Runtime + fabric contracts; B persistence/API/job lifecycle; C read-only runner/Avrea discovery then bounded adapters; D CACE recomputation and verifier receipts; E held-out routing and reproducible lab; F typed CAD/wiring and validators; G image/video adapters; H unified HUD and observation-to-requirement loop.

## Non-goals
No autonomous physical wiring, manufacturing release, unrestricted shell execution, automatic promotion/deployment or generated-media-as-proof. No certification or safety-compliance claim from prototype formulas.