# Merlin open-source model and inference fabric v1

Status: research-backed engineering design; candidate technologies are not installed or qualified by this document.
Repository integration target: `python/merlin/model_fabric.py` and the existing capability, council, CPU fabric, MCFC, event, registry and HUD systems.

## 1. Executive decision

Build a provider- and engine-neutral Model Fabric. Do not make AirLLM the universal runtime.

AirLLM is an important capacity experiment: layer/expert streaming can make very large checkpoints addressable on constrained VRAM. Its own release notes report a 2.8T sparse-MoE example at 3.72 GB peak VRAM, but also report roughly 900 seconds of one-time initialization and 292 seconds per generated token on the stated hardware. Those are project-reported results for that specific configuration, not general performance guarantees. AirLLM v4.0.0 also describes streamed LoRA training with frozen weights on disk and adapters on GPU. This makes it interesting for constrained capacity and research/fine-tuning experiments, but not the default interactive chat engine. Benchmark it against a smaller quantized model that fits in memory; fitting a checkpoint is not the same as practical inference.

Recommended candidate roles:

| Technology | Candidate Merlin role | When to use | Main caution |
|---|---|---|---|
| vLLM | Default GPU serving candidate | Interactive chat, council seats, batched inference | Requires compatible GPU/runtime; qualify exact model + engine |
| SGLang | Alternative high-throughput serving | Structured generation, prefix reuse, agent workloads | Compare with vLLM on Merlin's held-out workload |
| llama.cpp | CPU/edge/quantized local serving | Low-cost CPU inference, GGUF, small local models | Throughput and context performance depend heavily on hardware |
| MLX | Apple Silicon local inference | Mac development and local privacy | Apple-specific deployment target |
| Transformers | Reference implementation and compatibility baseline | Research, model inspection, custom pipelines | Not automatically the best concurrent serving runtime |
| AirLLM | Memory-constrained streamed inference | Rare large-model tasks, offline batch, fallback | Disk/PCIe-bound latency; not the default chat path |
| LiteLLM | Optional model API gateway | Provider normalization, retry/fallback, routing groups | Adds another operational component; don't duplicate Merlin's policy |
| Ray Serve LLM | Future distributed serving control plane | Multi-node replicas, disaggregated prefill/decode, scaling | Introduce only after single-node measurements show need |
| NVIDIA Dynamo | Future NVIDIA fleet optimization | Large multi-GPU / multi-node inference | Hardware- and operations-complexity dependent |

Sources:
- AirLLM releases and usage: https://github.com/lyogavin/airllm/releases
- AirLLM releases (including v4.0.0 and reported low-VRAM measurements): https://github.com/lyogavin/airllm/releases
- AirLLM project: https://github.com/lyogavin/airllm
- SGLang serving framework: https://sgl-project.github.io/
- llama.cpp inference and server: https://github.com/ggml-org/llama.cpp
- MLX Apple Silicon framework: https://github.com/ml-explore/mlx
- Inspect AI evaluation framework: https://inspect.aisi.org.uk/
- vLLM parallel serving: https://docs.vllm.ai/en/latest/serving/parallelism_scaling/
- Ray Serve LLM architecture: https://docs.ray.io/en/latest/serve/llm/architecture/overview.html
- LiteLLM routing: https://docs.litellm.ai/docs/routing
- NVIDIA Dynamo: https://developer.nvidia.com/dynamo
- Evaluation tools landscape: https://github.com/aglio-lab/ai-evaluation-tools

## 2. Existing Merlin facts that constrain the design

- `python/merlin/council_runtime.py` calls a loopback OpenAI-compatible endpoint and now performs up to six concurrent independent opening calls, isolates seat failures, and optionally runs a second concurrent cross-examination round. The endpoint still returns complete seat messages rather than token deltas.
- The local council is fail-closed unless `MERLIN_MODEL_QUALIFIED=1`; endpoint must be loopback HTTP.
- `python/merlin/app.py` already contains a remote OpenAI-compatible proxy configuration with HTTPS, explicit host allowlisting and a credential environment variable.
- `app.py` capability metadata reports local model execution as qualification-gated and other model capabilities as unqualified/unconfigured. Keep those truthful distinctions.
- `python/merlin/cpu_fabric/catalog.py` is a verified, bounded specialist module catalog with artifact hashes, base-model compatibility hashes, qualification metadata, memory limits and LRU residency. Reuse its governance principles; do not conflate its specialist modules with full model-serving backends.
- `python/merlin/resource_probe.py` measures effective CPU, memory, GPU and disk capacity and emits a digest-bound MCFC snapshot. Use measured capacity, not host marketing specifications.
- Existing `event_outbox.py`, telemetry, registry, graph and HUD runtime are the durable integration points.
- The HUD and event pump remain observers. Neither can grant model qualification or dispatch authority.

## 3. Model Fabric contract

Implemented in `python/merlin/model_fabric.py`:
- `ModelBackend`: engine, model and engine revisions, task scopes, data classifications, streaming/tool support, context window, concurrency and resource estimates.
- `ModelMeasurement`: task-specific held-out quality, p95 latency, tokens/sec, cost, peak RAM/VRAM, sample count, evaluation suite digest and result digest.
- `ModelQualificationReceipt`: binds the exact model revision, engine revision, held-out evaluation digest, result digest and security review digest.
- `ModelRouteRequest`: task, data class, quality/latency/cost/resource bounds and required features.
- `route_model`: fail-closed selection. No configured or merely reachable model is eligible without a matching approved receipt and task-specific measurement.

Routing policy:
1. Reject non-available backends.
2. Enforce data classification, task scope, streaming/tool features and memory budgets.
3. Require task-specific measurements.
4. Require exact matching approved qualification receipt for the current model + engine + evaluation/result digests.
5. Rank by quality first, then latency, throughput, cost and memory; explicit engine preference is only a tiny tie-breaker.
6. Return an explicit no-qualified-candidate decision instead of silently selecting an untested fallback.

This is a selection policy, not yet a live adapter, gateway or model server. No endpoint is called by this module.

## 4. Task-to-model routing

Use distinct profiles, not a single global model:
- HUD chat: low time-to-first-token, strong instruction following, safe tool protocol.
- Council seat: role-specific reasoning quality, context capacity and parallel request budget.
- Synthesizer: high quality, robust disagreement/evidence reconciliation, enough context for the transcript.
- Hermes decomposition: structured output and reliable task planning; must emit typed task proposals, not execute them.
- Code/build: code competence, tool calling and repository-context performance.
- Math discovery: mathematical reasoning, symbolic correctness, Lean tactic assistance; proof acceptance remains compiler/CACE-only.
- Vision/media: separate multimodal capabilities and artifact pipeline; never claim text-only models support them.
- Embeddings/reranking: retrieval-specific measured quality and latency.
- AirLLM capacity lane: long-running, low-priority, non-interactive requests when memory capacity matters more than latency.

Each profile gets a held-out evaluation suite. A single general benchmark score does not qualify a model for all tasks.

## 5. Council parallelism and streaming

After model backend qualification:
- The initial runtime now executes up to six independent council openings concurrently and records seat-completion telemetry. Next, place concurrency behind MCFC admission and per-seat resource budgets.
- Add per-seat token-delta streaming through the session gateway; current HUD renders completed seat responses after the council HTTP request returns. Keep failure isolation and add cancellation propagation.
- Cross-examination begins only after opening transcript is complete.
- Keep a maximum concurrency and deadline. Do not launch 12 unconstrained simultaneous requests.
- Use model routing per persona/task; the same model may serve multiple seats, but record that fact. Role prompts are perspectives, not independent agents.
- Preserve role-specific output hashes, provider/model revisions, usage and timing.
- Do not stream raw internal chain-of-thought. Stream concise conclusions, evidence, assumptions, confidence and tool/status events.

## 6. AirLLM qualification experiment

Do not install AirLLM into the production environment as a prerequisite. Run an isolated, opt-in experiment on a compatible worker with a pinned environment and model revision.

Compare at least:
1. A compact quantized model served by llama.cpp or vLLM (if compatible hardware).
2. A conventional Transformers baseline if memory allows.
3. AirLLM layer/expert streaming on the same model or a carefully documented closest supported model.

Measure:
- model load / initialization wall time;
- cold and warm time-to-first-token;
- p50/p95 inter-token latency and tokens/sec;
- peak RSS, peak VRAM and disk read throughput;
- prompt length and generated token count;
- output quality on the same held-out tasks;
- error rate, unsupported architecture count and restart/recovery behavior;
- model artifact size, license and exact revision.

Use at least 30 repeated samples per workload where practical, disclose sample count and confidence intervals, and do not compare unlike hardware without normalizing/reporting it. Test one interactive and one batch workload. AirLLM wins only if its capacity benefit outweighs measured latency and operational costs for a real Merlin task.

## 7. Resource and memory policy

- MCFC owns reservations and leases; runner telemetry owns measured consumption.
- Distinguish estimated RAM/VRAM, reserved budget and observed peak use.
- Model weights, KV cache, activations, tokenizer, runtime and concurrent sessions all consume resources.
- Reserve headroom for the OS, HUD, registry and workers; never allocate all reported memory to weights.
- Model residency is a bounded LRU pool. Pinned system models require explicit budget reservations and cannot be silently evicted.
- AirLLM disk streaming is a separate storage-I/O workload; measure free space, read bandwidth, page cache and checkpoint integrity.
- Keep downloads opt-in and checksum-pinned. Never download multi-hundred-GB weights automatically.
- Do not persist credentials, raw sensitive prompts or full environment dumps in telemetry.

## 8. Evaluation and qualification

Use complementary tools:
- Inspect AI / Inspect Evals for agent and tool-use task harnesses.
- lm-evaluation-harness for established academic benchmark coverage.
- promptfoo for prompt/model comparisons and red-team cases.
- Deterministic pytest checks for Merlin's API schemas, tool routing, cancellation, event lineage, safety and task-specific correctness.

Qualification receipt requirements:
- model repository + immutable revision and license;
- serving engine + immutable revision and runtime configuration digest;
- evaluation dataset/suite digest and held-out split identity;
- result digest, metrics, sample counts and uncertainty;
- security/privacy review digest and permitted data classes;
- resource profile and known limitations;
- reviewer identity and qualification time;
- expiry/requalification conditions.

No self-reported environment variable, model name, download success, or UI status can substitute for this receipt.

## 9. Integration order

P0: keep model capability states truthful and add the model-fabric contracts/tests.
P1: expose read-only model backend, qualification and measurement views to the existing HUD.
P2: implement an async session gateway with SSE, bounded concurrency, cancellation and deadlines.
P3: adapt the existing local OpenAI-compatible endpoint and remote allowlisted endpoint to a common adapter interface.
P4: connect route_model to real model inventory and held-out measurements; emit route decisions to the event outbox.
P5: parallelize council openings with MCFC admission and per-seat streaming.
P6: run AirLLM/vLLM/SGLang/llama.cpp experiments on an available compatible worker; store raw measurements and receipts in the registry.
P7: introduce LiteLLM only if it reduces adapter maintenance; choose either LiteLLM routing or Merlin routing as the policy owner, not both.
P8: introduce Ray Serve or Dynamo only after measured scale requirements justify multi-node orchestration.

## 10. Acceptance criteria

- Unit tests prove unqualified, unmeasured, stale-revision, data-class-incompatible and over-budget models cannot be selected.
- Route decisions are deterministic for identical input evidence.
- Model route decision includes exclusions and exact measurement/receipt references in the eventual event contract.
- Chat and council streams support cancellation and bounded concurrent execution.
- Each council role can fail without erasing completed seats.
- No provider fallback silently crosses a data-class or qualification boundary.
- AirLLM is accepted only on measured results; it is never called low-latency merely because it fits in VRAM.
- Resource reservations and measured consumption remain separate.
- Full test suite and held-out model qualification pass on a real runner before production status is granted.

## 11. Next vertical slice

Connect one already-configured local OpenAI-compatible endpoint to the session gateway through a model backend record. Use a deterministic stub in CI, but require a real qualification receipt for production route selection. Then stream one chat turn and six bounded council seats to the HUD, persist the transcript/artifact references, and expose model health, measurements and qualification in the capability panel.
