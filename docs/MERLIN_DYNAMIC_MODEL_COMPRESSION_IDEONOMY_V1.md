# Merlin Dynamic Model Compression and Conditional Execution — V1

## Thesis
Do not treat a large model as one indivisible resident object. Keep a compact shared core and a catalog of independently versioned specialist modules. Route each request to the smallest sufficient execution path; load specialists on demand and unload under memory pressure. The router must cost less than the compute it saves.

## Research basis
- SLIM (ICML 2025) combines quantization, structured sparsity, and low-rank error compensation.
- MC# (2025 preprint) studies significance-aware mixed precision and online expert pruning for MoE models.
- DynaExq (2025 preprint) studies hotness-aware dynamic expert precision and asynchronous switching.
- 2026 on-device LLM research frames optimization across accuracy, latency, energy, and memory.
These results motivate experiments; they do not guarantee wins on our CPU runner.

## Candidate architecture
1. Compact core: a reliable generalist model at a measured precision.
2. Capability catalog: specialist adapters/modules with manifests, hashes, declared memory cost, compatible base-model hash, and task scope.
3. Router: estimate task, confidence, expected specialist benefit, load cost, and available resources.
4. Conditional executor: core-only when sufficient; otherwise activate one specialist or a small approved set.
5. Memory manager: bounded resident set, hotness/LRU tracking, allowlisted modules, clean unload, and explicit pinning rules.
6. Escalation: if confidence is low or verification fails, use a stronger approved specialist/model; never silently relax quality thresholds.
7. Evaluator: task quality, latency, peak RSS, disk footprint, load/unload overhead, fallback rate, and energy where measurable.

## Ideonomy search dimensions
- Precision: fp16, int8, int4, mixed precision.
- Structure: dense, structured sparsity, low-rank correction.
- Capability form: shared backbone, adapter, specialist expert, distilled student.
- Routing: core-only, top-1, top-2, confidence-triggered escalation.
- Activation depth: full depth, validated early exit, adaptive depth.
- Residency: always resident, hot cache, on-demand load, memory-pressure eviction.
- Context: full prompt, retrieval-selected context, compressed context, bounded KV cache.
- Decode: ordinary autoregressive, speculative draft/verify with a compatible draft model.

## Ranking objective
Do not collapse quality and safety into one opaque score. Apply hard gates first: task-quality non-inferiority, no policy regression, deterministic loading, valid module/base hashes, resource limits, and rollback. Then report a Pareto frontier across quality, time-to-first-token, tokens/sec, peak RSS, disk size, load overhead, and fallback rate. Any scalar screening score is secondary and must expose its weights.

## First experiments
A. Baseline a small generalist model on CPU: model bytes, RSS, prompt processing, generation speed, task quality.
B. Compare supported quantization levels with identical prompts and evaluation.
C. Add one narrow specialist adapter/module; compare always-loaded and on-demand modes.
D. Compare core-only vs core-plus-specialist routing on a fixed task suite; measure router overhead and fallback quality.
E. Stress load/unload cycles and verify no stale state, hash mismatch, or unbounded RSS growth.

## Caveats
- Quantization reduces weight memory but does not automatically improve speed on every CPU.
- Unstructured sparsity may not accelerate inference without a matching kernel; prefer structured forms with hardware/runtime support.
- Dynamic loading saves resident memory but adds latency and I/O; measure break-even and maintain a small hot set.
- Early exit and aggressive expert pruning can harm rare or difficult tasks. Use calibrated confidence and verifier-triggered escalation.
- Adapters require strict base-model compatibility; enforce hashes and explicit manifests.

## CACE contract
Typed capability fields: model_id, module_id, base_hash, module_hash, task_scope, memory_estimate, precision, load_policy, confidence_threshold, verifier_id, rollback_ref. Router proposals are non-authoritative. Loading is limited to approved artifacts in an allowlisted catalog. Promotion requires reproducible benchmarks, task-quality gates, independent verification, and rollback. Capability grows, authority never expands.

## First target
Do not compress the largest available model first. Benchmark a small generalist and prove dynamic specialist activation on one narrow domain before scaling up.
