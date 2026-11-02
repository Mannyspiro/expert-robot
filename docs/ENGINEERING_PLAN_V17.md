# Merlin inductive engineering plan v17 — 2026-11-02

## North star

Deliver a local-first Merlin workbench that uses Expert Robot as its bounded execution runtime, CACE as its typed capability/formal layer, Hermes Agent as an optional specialist worker, and a provenance-first research system. Merlin should help build and improve its own modules, but candidate generation and promotion remain separate. **Capability grows; authority never expands automatically.**

This plan is updated from observed requirements in the current request, prior project discussions, the v16 research package, the v31 sovereign package, the v10 unified intake archive, and the live Expert Robot PR/Avrea runs. Supplied source claims are not treated as verified unless independently reproduced.

## Current branch baseline

Repository: Mannyspiro/expert-robot  
Branch: feat/merlin-hermes-kokoro-integration-20261102  
Draft PR: #67 — Add Merlin, Hermes coding, Kokoro voice, engineering IR and network inference.

### Verified in this iteration

- Hermes Agent source checkout completed on Avrea; recorded upstream revision 5e7c2b254d414e4e25105231f818f385fee67469.
- NousCoder-14B Q4_K_M downloaded on Avrea: 9,001,754,752 bytes; SHA-256 matched 9cc51afc755319db42a6324baf3395436cce5954dc87df95d3b9e7d625610624. Model weights remain in runner cache / ignored model path, not Git.
- Kokoro-82M ONNX produced a real mono WAV artifact: 24 kHz, 16-bit, 4.75 seconds. The live synthesis workflow passed. This verifies synthesis output, not subjective voice quality or multi-browser playback.
- Avrea CI passed C++ build/tests, existing policy and regression checks, formal dependency lock, CACE bridge and collar checks, plus Hermes/voice contracts, geometry/netlist tests and the new research-core tests. The workflow's final run status must be read from GitHub before release.
- Typed geometry IR supports mm/cm/m/in conversion, basic mesh face and closed-solid edge checks, bounding boxes and OpenSCAD export.
- Typed netlist IR checks component/pin references, duplicate assignment, basic supply-ground shorts and declared voltage/current ratings. It is not circuit simulation or electrical safety certification.
- Research core adds artifact-backed evidence classes, idea candidate rejection/ranking, analogy invariant checks and fail-closed RSI gates.

### Observed failure / gap

- The first NousCoder llama.cpp CPU inference build succeeded, but its first chat-completion smoke returned empty content. A second diagnostic run was configured with Qwen3 enable_thinking=false, larger output budget, content/reasoning fallback and always-uploaded diagnostics. It has not yet established a qualified inference result.
- The v16 package reports 541 passed / 2 skipped with nine inherited modules excluded. An independent test collection attempt against the included merlin_v11/MERLIN source stopped because merlin.vendor.cace_engine_v5 is absent. Treat the 541 count as a supplied report, not an independently reproduced full-suite result.
- Exact-head Lean proof qualification, real Hermes agent task execution through the Expert Robot broker, full council playback, image/video adapters, and physical CAD/electrical qualification remain open.
- v28 HUD is a visual/front-end prototype. Its self-described simulated modules must not be presented as real agent execution.

## Product architecture

1. Merlin Workbench: conversation, project context, evidence ledger, plan updates, voice capture, council playback, idea exploration and artifacts.
2. Expert Robot: local model routing, task execution, sandbox, tool broker, repository adapters, event/receipt logging and compute budgets.
3. Hermes Agent: optional coder/research worker, installed source-only by default, connected to local NousCoder and constrained by Expert Robot permissions.
4. CACE: typed contracts, capability registry, graph/geometry semantics, Lean formalization, qualification receipts and authority policy.
5. Research Miner: source ingestion, citations, claim records, deductive/inductive reasoning, lacuna ranking and reproducible experiments.
6. Specialists: image/video generation, parametric CAD, wiring/netlists, biochemical kinetics, evolutionary search and mathematical simulation.
7. Council: distinct architect, skeptical scientist, formal-methods reviewer and builder perspectives; sequential TTS playback with interrupt/stop and a text transcript.

No subsystem is allowed to invent tool results, evidence, test completion, model availability or external state.

## Prioritized build sequence

### P0 — Make the MVP one connected system
- Define versioned JSON contracts for health, model chat, TTS, council, research, idea ranking, geometry validation, netlist validation and evidence receipts.
- Add a single Merlin API facade that routes to local model services and the Expert Robot runtime.
- Store project records, prompts, outputs, evidence references, approvals and plan deltas in SQLite with append-only event IDs.
- Add a status view that distinguishes AVAILABLE, NOT_CONFIGURED, RUNNING, BLOCKED, FAILED and QUALIFIED.
- Acceptance: one voice or text request can be received, routed, answered by a configured local model, reviewed by the council, spoken by Kokoro, and saved with a provenance record.

### P1 — Qualify local coding
- Complete NousCoder inference smoke on Avrea; capture raw JSON and server log even on failure.
- Validate actual code, not just non-empty text: request a deterministic clamp function, extract code, execute unit cases, and compare expected outputs.
- Run a fixed held-out coding set against the existing Qwen3-Coder role. Measure pass rate, tool compliance, latency, peak RAM and reproducibility.
- Only then enable Hermes Agent against the local endpoint. First task runs in read-only workspace mode; write operations go through Expert Robot's approval and sandbox.
- Keep existing Qwen role unchanged until independent comparison supports a switch.

### P2 — Council and voice
- Use Kokoro as the default local voice backend; browser speech is a fallback only.
- Map distinct council seats to stable voice IDs and speaking styles, while preserving the exact text transcript.
- Sequential playback, stop/cancel, retry, audio caching and no logging of raw microphone audio by default.
- Acceptance: repeatable multi-seat playback on desktop and iOS Safari with browser autoplay constraints handled through explicit user initiation.

### P3 — Visual and drafting pipeline
- Build a shared typed design IR: coordinate frames, units, constraints, materials, topology, dimensions, revisions and source provenance.
- Route image prompts to an image adapter; route motion/video prompts to a video adapter. Store prompt, model, version, output hash, rights and resource cost.
- Treat images as ideation only. Extract dimensions/geometry into typed IR before CAD generation.
- Add parametric OpenSCAD generation, SVG/DXF drafting and mesh validation. Add independent kernel checks for self-intersection, manifoldness, units, tolerances and volume.
- For wiring, add netlist-to-schematic layout, ERC/DRC and SPICE adapters. Existing structural preflight is not sufficient to energize a design.
- Acceptance: a generated concept can be revised through typed parameters, exported, reopened in a target CAD tool and independently checked.

### P4 — Research and biochemistry
- Integrate Research Miner v19 behind a versioned adapter after re-running its included tests from the exact source bundle.
- Use source hashes, citations, retrieval time, license, assumptions, uncertainty and falsifiers for every claim.
- Add biochemical reaction networks, enzyme kinetics, gene-regulatory networks and evolutionary simulations as separate unit-aware models.
- Validate each solver against analytic cases, conservation laws, manufactured solutions and published reference data.
- No clinical claims, wet-lab instructions or fabrication conclusions from toy simulations.

### P5 — Ideonomy and alien-lacuna science
- Generate candidates by recombining established methods across geometry, graph theory, control, information theory, chemistry, biology and computation.
- Every candidate must state mechanism, assumptions, constraints, observable, falsifier and cheapest discriminating experiment.
- Reject undefined mechanisms, violated dimensions, missing boundary conditions, non-falsifiable language and unbounded resource claims.
- Rank survivors by novelty, feasibility, evidence fit, testability and resource cost; preserve rejected candidates with reasons.
- Alien is a search metaphor for unfamiliar cross-domain combinations, never a claim of extraterrestrial source or validity.

### P6 — Verified reframing
- Formalize the original problem's entities, operations, invariants, boundary conditions and failure modes.
- Build a mapping to a simpler target problem.
- Require explicit preservation of all relevant invariants and compatible boundaries.
- Solve the target, translate back, and run the result against the original problem.
- Reject analogies that fail any invariant or boundary check.

### P7 — CACE and formal qualification
- Reconcile CACE snapshots against live repository heads; preserve version provenance and do not combine versioned modules blindly.
- Use CACE as typed source of truth; avoid duplicate capability engines.
- Pin Lean toolchain and mathlib revision. Run lake build, theorem inventory, axiom audit and receipt verification at exact commit.
- Keep unproved statements conditional with explicit assumptions; never infer proof from source presence or old logs.

### P8 — RSI, evolution and compute governance
- Isolated candidate branch and reproducible build.
- Matched compute budgets, baselines, held-out tasks, ablations and confidence intervals.
- Independent review, rollback, authority non-expansion, human approval and immutable receipts.
- Optimize information gain against cost, variance and diminishing returns.
- Candidate generation may be automatic; promotion never is.

## Problem-reframing protocol

When blocked:
1. Write the exact failing operation and observable error.
2. Identify invariants and boundary conditions that must survive.
3. Find a simpler problem with a known solver.
4. Write the mapping explicitly, including entities and operations.
5. Verify invariant preservation before using the analogy.
6. Solve the simpler problem and translate back.
7. Test against the original acceptance criteria.
8. If the mapping fails, revise the abstraction or abandon it.

## Compute policy

- Prefer the user's Avrea self-hosted runner (avrea-ubuntu-latest-8-vcpu) for builds, model acquisition, Kokoro synthesis and benchmarks.
- Use OCI cace-oci-a1 as a fallback only when Avrea is unavailable or the job needs a distinct environment.
- Avoid repeated 9 GB model downloads: cache verified weights and provenance; never commit them.
- Heavy NousCoder inference qualification is manual-only to avoid rebuilding llama.cpp on every PR commit.
- Keep standard CI fast and deterministic. Avoid parallel duplicate workflows that contend for the same runner.

## Inductive plan update rule

For every new requirement or failure append:
observation → source/receipt → gap → smallest analogous subproblem → acceptance test → result → plan delta.

A feature is not complete because a UI exists, a package downloads, a prompt returns text, or a test is merely listed in an old report. Only reproducible current-head evidence changes its status.


## Inductive plan update v18 — network-native inference

Observed requirement: Merlin must not depend on hosting all model weights locally. Treat model execution as a network service: weights stay on remote provider/worker hardware and Merlin streams generated output, audio chunks and artifacts over authenticated connections.

### Implemented on the current feature branch
- Added an OpenAI-compatible remote model route to `POST /api/chat`.
- Requires HTTPS, exact hostname allowlisting, runtime-only bearer credentials and a separate remote qualification flag.
- Supports incremental Server-Sent Events passthrough when the caller requests `stream: true`; retains non-stream JSON and separately gated local llama.cpp mode.
- Added tests for HTTPS and allowlist rejection, plus example configuration and an operator guide.

### Immediate next steps
1. Run Avrea CI and fix any test/regression failures; verify the live stream with a fake SSE upstream test that proves chunks arrive before completion.
2. Add request cancellation, deadlines, bounded concurrency and connection pooling using an async HTTP server/client; keep the current loopback server as a low-concurrency fallback.
3. Add provider registry and task-role routing (general, reasoning, coding, research, vision, media) with model capability metadata, context limits, pricing and qualification receipts.
4. Add telemetry for TTFT, tokens/sec, end-to-end latency, error rate and cost per successful task; do not record prompt bodies or secrets.
5. Add council fan-out/fan-in: stream the lead voice first, then independent critiques; synthesize sequentially with Kokoro chunking and cancellation.
6. Keep Avrea/OCI for private jobs, repository tests, simulations, indexing, local fallback and workloads where data must not leave the worker.

### Architectural rules
- Stream inference results, not weights per request.
- Never claim fastest without comparative benchmarks on identical held-out tasks.
- No silent provider fallback that changes where private prompts are sent.
- Provider/model qualification is independent from network connectivity; reachability alone is not qualification.
- Secrets stay in runtime secret storage; never commit keys.
- Capability grows; authority never expands automatically.


## Inductive plan update v19 — hybrid compressed intelligence and hot-swap

Observation: network inference solves the model-size ceiling but adds network dependency, privacy decisions and provider latency. New requirement is to compress local inference and swap weights/data/adapters dynamically, while preserving remote expert access.

Source-backed research:
- llama.cpp supports GGUF quantization, mmap/lazy tensor loading, selectable KV-cache precision and device offload.
- llama-swap provides on-demand process/model switching across compatible OpenAI/Anthropic APIs and local multimodal backends; evaluate as a replaceable supervisor.
- LLM Compressor provides PTQ/GPTQ/AWQ/SmoothQuant/AutoRound/rotation methods, activation and KV-cache quantization, and sequential offload, subject to compatible hardware/runtime.
- NASA NPO-51334-1 is explicitly Open Source and includes image preprocessing, augmentation and TensorFlow model compression; relevant to vision pipeline experiments, not general LLM compression.
- The adaptive distributed compression patent US12375101B1 found in this pass is assigned to Atombeam Technologies Inc., not NASA. It is a research lead, not free code or a blanket patent license. No directly relevant NASA-owned patent was verified in this pass.

Architecture decision:
1. Resident local quantized generalist for ordinary chat, routing and offline fallback.
2. On-demand local specialists with model leases, idle unload, optional prewarm, and strict session/KV isolation.
3. Optional LoRA adapters pinned to base-model/tokenizer hashes.
4. Context, retrieval, tool packs and datasets hot-swapped independently of model weights.
5. Qualified remote models for difficult tasks; do not silently move private data across providers.
6. Council uses independent models/evidence paths; stream the lead answer first and preserve a verbose written debate transcript.

Parrondo-inspired evaluation:
- Compare local-fast A, remote/specialist B, adaptive switching, and council under equal task and resource budgets.
- The hybrid only qualifies if held-out net utility exceeds each fixed policy after quality, latency, cost, privacy and unsupported-claim penalties.
- Require ablations, confidence intervals and correlated-error analysis. Do not assume mixing strategies creates an improvement.

Next execution:
H1 inventory hardware/runner RAM, VRAM, disk, CPU and existing artifacts; establish local-vs-remote cold/warm benchmarks.
H2 prototype one 1-4B-class GGUF generalist, compare Q4/Q5/Q8 with identical held-out tasks.
H3 prototype llama-swap isolated behind Merlin adapter; add request leases, idle unload, prewarm and bounded concurrency.
H4 add adapter manifests and per-task context packs with compatibility checks.
H5 add task-role router and Parrondo evaluation.
H6 implement verbose council transcript + streamed lead voice and optional full-debate playback.
H7 connect RSI candidate generation to benchmark, independent verification, human approval, signed receipt and rollback.

Acceptance gates:
- Quantized local core retains required task quality and improves measured memory/latency.
- A→B→A model switching produces no corrupted response, stale session state, cross-user KV reuse or unbounded memory.
- Adapters incompatible with base model/tokenizer fail closed.
- Hybrid policy beats fixed baselines on held-out tasks with confidence intervals and no privacy violations.
- Council demonstrably improves quality over the best single model, with incremental latency/cost disclosed.

Implementation note: this update records a plan and research shortlist only. No model weights, NASA source, llama-swap or LLM Compressor have been downloaded/integrated; no hardware inventory or benchmark has been run. Keep current gateway in place until prototype gates pass.
