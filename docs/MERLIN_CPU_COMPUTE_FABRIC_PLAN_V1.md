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
