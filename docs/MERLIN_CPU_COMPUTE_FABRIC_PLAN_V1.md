# Merlin CPU Compute Fabric — V1

## Objective
Build a CPU-native parallel compute layer for workloads commonly assigned to GPUs. This is not GPU emulation: it uses CPU vectorization, cache-aware tiling, bounded parallel scheduling, and quantized operators where validated.

## Ranked experiments
1. Cache-aware matrix kernels: establish correctness and throughput across tile sizes.
2. Scheduler comparison: serial, fixed chunks, and bounded thread-pool execution; verify identical outputs.
3. Vector/tensor primitives: AXPY, reductions, quantized integer dot products, then attention primitives.
4. Ideonomy search: enumerate combinations of tile size, chunk size, worker count, precision, and data layout; rank by measured throughput, memory, numerical error, repeatability, and runner cost.
5. CACE adapter: expose only benchmarked, typed, bounded capabilities; promotion requires reproducibility and rollback.

## Experimental contract
Every run records hardware and runtime metadata, workload dimensions, parameters, seed, elapsed time, throughput, memory observations where available, numerical error, and verification status. Unknown hardware limits remain unknown rather than inferred. Benchmarks use fixed seeds, bounded dimensions, and explicit timeouts.

## Initial operating profiles
- Standard: target the observed 8-core runner and approximately 30 GB available memory, subject to cgroup limits.
- Constrained: 16 GB memory budget; smaller matrices and bounded queues.
- No GPU requirement. SIMD features must be detected at runtime; never assume AVX-512 or AMX support from the CPU model name alone.

## Promotion rule
Capability grows, authority never expands. No generated kernel is promoted based on predicted speedup alone. Require deterministic tests, numerical tolerance checks, independent benchmark reproduction, resource bounds, and rollback.

## Known benchmark issue
The existing Ollama baseline downloaded qwen2.5:7b successfully, but inference failed because the inference step's MODEL environment variable did not use the same default expression as the download step. Fix this before rerunning; do not download another model.

## MCFC workload contracts and execution leases

MCFC is the virtual compute fabric: it owns typed CPU, memory, and GPU resource
availability, compute budgets, workload admission, expiring/revocable leases,
and runtime resource telemetry. It does not own geometric coordinate transforms
(those belong to XMG) and it does not qualify engineering results (that belongs
to independent CACE verification and human review).

The first typed reference contract is implemented in
`python/merlin/cpu_fabric/leases.py`:

- `ResourceRequest`: CPU cores, memory bytes, GPU count, and GPU memory bytes.
- `CapacitySnapshot`: measured capacity, observation time, source, and evidence
  SHA-256. Unknown GPU fields remain `None`; they are never inferred.
- `WorkloadRequest`: workload ID, capability, resource request, wall-time limit,
  compute-budget units, and priority.
- `ExecutionLease`: explicit resource reservation, issue time, wall-time deadline,
  expiry, capacity evidence hash, execution-only authority, and lifecycle state.
- `LeaseBook`: bounded admission, idempotent workload IDs, resource reservations,
  expiry, completion, revocation, and runtime telemetry.
- `cad_wire_route_request()`: CPU-only CAD wire-route workload adapter. The caller
  must supply memory, wall-time, and compute-budget estimates; the adapter does
  not invent them.

The route evidence receipt in `python/merlin/route_evidence.py` binds the
completed MCFC lease and its capacity-evidence hash to the project, assembly,
frame graph, route output, router version, and source revision. CACE ledger
ingestion re-verifies those inputs and adds experiment evidence only. It does
not change hypothesis status or grant promotion authority.

Current implementation boundary: `LeaseBook` is an in-process reference
admission ledger. Durable multi-process lease storage, worker heartbeats,
preemption, fair scheduling, and measured live resource probes are future work.
The test capacity fixture is synthetic and must not be reported as actual runner
capacity.

## CAD/wiring workload routing

The current CPU-only `cad.wire_route_proposal` task maps to a one-core request,
with memory and runtime bounds supplied by the orchestrator. GPU use is not
requested because the current route planner is a deterministic CPU algorithm.
If a later CAD/solver workload requests GPU resources while GPU capacity is
unknown, MCFC rejects admission pending a fresh resource probe.

Merlin's CAD/wiring path now separates:
1. logical project and pin/net topology;
2. XMG coordinate-frame transforms and physical pin placement;
3. candidate 3D route geometry;
4. review-labelled wiring exports;
5. electrical/thermal/manufacturing screening;
6. CACE evidence verification and human approval.

These are distinct artifacts and evidence gates. A route visualization is not a
release schematic; a qualification screening report is not certification.

## MCFC queue scheduling increment

`python/merlin/cpu_fabric/workload_scheduler.py` adds a deterministic
priority/FIFO admission queue over the typed lease book. It dispatches work that
fits the current measured capacity, skips temporarily unfit work rather than
head-of-line blocking, and retains blocked jobs for a later dispatch. The
scheduler issues leases; it does not start processes, preempt workers, or persist
queue state across restarts. Priority is a queue-order field, not an entitlement
to exceed resource limits.

Avrea CI tests priority/FIFO ordering, blocked-job bypass, redispatch after
resources are released, cancellation, and duplicate workload IDs. This remains
a reference scheduler; durable queue state, distributed worker heartbeats,
fairness/aging, and real worker execution are not yet implemented.

### First measured Avrea snapshot (2026-11-04)

Resource-probe run #8 measured 8 effective CPU cores and 31,609,856,000 bytes
of effective memory. GPU capacity and compute-budget units were both unknown.
Snapshot evidence SHA-256:
`05d57c837e3de8f3542a6fdf35a6fbf1fa2cd1c5db19e07fffe0058b8a5600a6`.
This snapshot is ephemeral and must be refreshed for each execution environment;
it does not authorize a lease by itself because compute-budget capacity is
unknown.
