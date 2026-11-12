# Merlin Hybrid Compressed Intelligence v1

Date: 2026-11-02
Status: architecture proposal + source shortlist; not yet implemented or benchmarked

## Executive decision

Use a hybrid, model-independent intelligence fabric. Keep a small quantized generalist and deterministic tools warm locally; load specialist models/adapters only when needed; route tasks to remote inference when local quality, memory, or latency is insufficient. Do not attempt to compress one giant model into every role.

### Three resource layers

1. **Resident core (local/worker):** small instruct model for ordinary chat, routing, extraction, summarization, and offline fallback. Target 1-4B class initially, but select by benchmark and memory budget, not parameter count alone. Quantize to GGUF Q4_K_M or a comparable supported 4-bit scheme; compare Q5_K_M and Q8 for quality-sensitive tasks.
2. **Hot-swappable specialists:** coding, mathematics, vision, embeddings/reranking, speech, and image/video models. Use one process manager to load/unload compatible model servers on demand. Keep only frequently used models resident; prewarm the next likely specialist when the router has high confidence.
3. **Remote expert tier:** qualified HTTPS model providers for tasks where local capability is inadequate. Stream response tokens; do not download weights for each request. Provider choice and data classification are explicit.

## What "hot swap data" should mean

Do not treat all model state as one thing:
- **Weights:** model parameters; expensive to load. Hot-swap whole models only at task boundaries, using a model manager.
- **Adapters (LoRA):** small task/domain deltas; load/unload against a compatible base model. Pin base model hash, adapter hash, tokenizer and adapter compatibility metadata.
- **KV cache:** per-session attention state; quantize or offload when supported. Never reuse across users or incompatible model/tokenizer/session identities.
- **Context and memory:** retrieved summaries, code chunks, embeddings, and working sets. Swap these cheaply per task without changing weights.
- **Tools and capability packs:** deterministic executables, schemas, CAD templates, proof checkers, chemistry calculators and simulation libraries. Load by capability manifest and sandbox policy.
- **Datasets/calibration:** task-specific data is versioned and mounted only for the relevant job; no automatic fine-tuning on arbitrary conversations.

## Compression and serving techniques

### Weight quantization
- Start with 4-bit quantized weights (GGUF Q4_K_M for llama.cpp-compatible models).
- Compare 5-bit and 8-bit candidates on held-out tasks; keep a higher precision layer/model if quality drops on reasoning, code or math.
- Use calibration-aware methods (AWQ/GPTQ/AutoRound or compatible LLM Compressor recipes) when the model/runtime/hardware supports them.
- Treat FP8/FP4/MXFP formats as hardware-specific options, not universal defaults.
- Record model card/license, source revision, conversion command, quantization recipe, calibration dataset hash, artifact hash, perplexity and task-suite results.

### Runtime memory
- Quantize KV cache (e.g. Q8 or Q4 where supported), measure long-context degradation.
- Use mmap/lazy loading and CPU/GPU layer offload when supported by the runtime.
- Keep context windows bounded with retrieval and structured summaries; do not stuff all chat history into every prompt.
- Cache embeddings and deterministic tool results with tenant/session boundaries and TTL.
- Stream large media and artifact chunks; do not base64-encode huge files into prompt text.

### Specialist adaptation
- Prefer retrieval + tool use first; use LoRA adapters when repeated examples show a stable domain gap.
- Distill repeated successful workflows into small models only with licensed training data, held-out evaluation and rollback.
- Do not continuously mutate production weights from live conversations.
- Preserve a fixed reference model and golden benchmark to detect catastrophic forgetting.

## Model manager / hot-swap layer

Candidate: mostlygeek/llama-swap (MIT; verify current repository license and dependency notices at vendoring time). It advertises on-demand swapping for llama.cpp/vLLM and compatible image/audio backends, OpenAI-compatible endpoints, status and unload APIs. Evaluate it as an external process supervisor, not as the source of truth for model permissions.

Alternative/runtime components:
- ggml-org/llama.cpp (MIT): portable GGUF inference, quantization, mmap/lazy loading, KV cache types and device offload.
- vllm-project/llm-compressor (Apache-2.0): PTQ/GPTQ/AWQ/SmoothQuant/AutoRound/rotation-based methods, activation/KV cache quantization and sequential offload; use only with compatible vLLM hardware/runtime.
- Existing Merlin remote gateway: keep as a provider adapter; evolve to async connection pooling, cancellation, deadlines, backpressure and per-provider circuit breakers.

Before adding any dependency: pin release/commit, scan transitive licenses, run SBOM/license scan, inspect security posture, record NOTICE files, and isolate it behind a Merlin adapter.

## Parrondo-inspired ensemble scheduling

Use Parrondo's paradox as a testable scheduling hypothesis, not as a claim that arbitrary model ensembles become better:
- Policy A: fast local generalist. It is cheap but may fail hard tasks.
- Policy B: expensive specialist/remote expert. It is individually costly and may have different failure modes.
- Switching policy: select A or B using uncertainty, task type, historical calibrated accuracy, queue delay, privacy class and remaining budget.
- Council policy: two independent solvers produce candidate answers; a skeptic searches for counterexamples; a verifier checks objective claims/code/proofs; a synthesizer resolves only evidence-backed disagreements.

The combined policy is useful only if the measured net utility beats each fixed policy after latency, cost, privacy, and error penalties. Avoid correlated model copies that merely repeat the same mistake.

Score:
U = quality_gain - lambda_latency * latency - lambda_cost * cost - lambda_risk * unsupported_claims - lambda_privacy * policy_violation

Evaluate on held-out tasks with fixed budgets, randomized order, confidence intervals, ablations (A only, B only, switch, council), and a record of when switching helps or hurts. Do not promote a policy based on cherry-picked examples.

## Council voice behavior

- After a voice prompt, first stream a concise acknowledgement/lead response so the system feels immediate.
- Run independent council seats in parallel with distinct written mandates: Architect, Scientist, Engineer, Skeptic, Evidence Auditor, and CACE/Lean Verifier.
- Keep debate verbose in the research transcript: each seat states assumptions, strongest argument, evidence, uncertainty, counterargument and falsifier.
- Synthesize a final recommendation with dissent preserved. Do not make the user listen to every long debate by default.
- If voice playback is enabled, play the lead answer first; queue council summaries and allow "play full debate". Use chunked TTS, interrupt/cancel, and speaker labels.
- Council roles are prompts and evaluation contracts, not proof of independent expertise. Use different model families or evidence paths where possible.

## NASA and public-code research

Verified candidate:
- NASA Software Catalog entry NPO-51334-1, "Convolutional Neural Networks for Spacecraft Pose Estimation", is explicitly marked Open Source and describes image preprocessing, data augmentation and TensorFlow model compression while retaining spatial detail. Its NASA catalog entry links directly to a GitHub download. This is a possible vision-pipeline reference, not a general LLM compressor and not yet integrated.

NASA catalog access policy:
- "Free of charge" does not mean every catalog item is unrestricted. Check each item's Release Type. Use Open Source or General Public Release only when the terms allow the intended use; do not use U.S. Government Purpose, U.S.-only, project or other restricted items without satisfying their release terms.
- NASA software release status is distinct from patent ownership/licensing. A patent disclosure is not a code download or blanket license to practice every claim.

Patent search finding:
- The adaptive neural-network compression patent surfaced in this research, US12375101B1, lists Atombeam Technologies Inc. as assignee, not NASA. It describes edge/central compression, temporal modeling, adjustable quantization and feedback. Treat it as a research lead only; it is not NASA code, not a free implementation, and its claims require independent legal review before any commercial implementation that may overlap.
- No NASA-owned patent specifically covering the proposed Merlin LLM hot-swap/compression stack has been verified in this pass. Continue searching NASA's public patent/technology portfolio by assignee and claim language; record patent number, owner, jurisdiction, legal status and relevant claims. This is not a freedom-to-operate opinion.

## Source and license policy

The request to reuse code without attribution is not adopted. Merlin can use code at no monetary cost where the license or NASA release terms permit, but it must preserve required copyright notices, license texts, NOTICE files and attribution. A patent publication being public to read does not grant patent rights; public source code is not automatically public domain. Prefer MIT, BSD-2/3-Clause and Apache-2.0 dependencies where compatible, but preserve every required notice and review Apache patent terms. Avoid copyleft dependencies unless the project's distribution model intentionally accepts those obligations.

## Implementation phases and acceptance gates

### H1 — inventory and baseline
- Inventory current worker RAM, GPU/VRAM, disk, CPU, runner quotas and current model artifacts.
- Establish local resident-model baseline, remote baseline, cold-start and warm-start latency, tokens/s, peak RAM/VRAM, task accuracy, cost/task and privacy class.
- Acceptance: reproducible benchmark JSON and artifact provenance.

### H2 — local compressed core
- Add one small GGUF generalist behind the existing model adapter.
- Compare Q4_K_M/Q5_K_M/Q8 using identical prompts and deterministic settings.
- Acceptance: no material regression on basic chat/tool-routing suite; measured memory/latency improvement.

### H3 — hot-swap supervisor
- Prototype llama-swap in an isolated branch/container; configure only approved model IDs and local loopback upstreams.
- Add leases so active requests prevent model unload; unload only after idle timeout; support prewarm and bounded concurrent models.
- Acceptance: switch A→B→A without corrupted responses, stale session state, leaked memory or cross-session KV reuse.

### H4 — adapters and dynamic data
- Add adapter manifest, base-model hash pinning, per-task context packs, retrieval cache and optional LoRA activation.
- Acceptance: incompatible adapter/base combinations fail closed; session data remains isolated.

### H5 — hybrid router + Parrondo evaluation
- Implement task-role routing and adaptive switching among local, specialist and remote models.
- Compare fixed vs switching policies on held-out task suite and equal budgets.
- Acceptance: net utility improves with confidence intervals and no privacy-policy violations.

### H6 — verbose council and voice
- Parallel independent seats, evidence ledger, dissent preservation, streaming lead response and chunked TTS queue.
- Acceptance: council adds measurable factual/code/proof quality beyond best single model, with acceptable incremental latency and cost.

### H7 — RSI loop
- Candidate branch → matched-budget benchmark → independent verifier → human approval → signed release receipt → rollback path.
- Optimize quality per joule/cost and information gain per unit time, not raw model size.
- Candidate generation may be automatic; model promotion and authority changes require approval.

## Reframing protocol

When an engineering task blocks:
1. State the exact failing operation, expected behavior and observed error.
2. Extract invariants, constraints, units, trust boundaries and acceptance tests.
3. Translate to the simplest analogous problem (e.g. model swapping as process scheduling; context swapping as cache replacement; model routing as a constrained bandit).
4. Write the mapping explicitly and prove/check invariant preservation.
5. Solve the analogue, translate back, then run the original acceptance tests.
6. If the analogy loses an invariant or changes the objective, reject it.

## Current status

This document is a research-backed design proposal only. No new quantized model, llama-swap dependency, NASA source, or adapter has been downloaded or integrated in this commit. No hardware inventory or local-vs-remote benchmark has been run. The next concrete implementation is H1 inventory plus an isolated llama-swap prototype; do not replace the existing Merlin gateway until the prototype passes its acceptance tests.
