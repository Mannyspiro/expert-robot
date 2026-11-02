# MERLIN master project handoff — 2026-11-02

This is a consolidated engineering handoff from retained project discussions, current repository state, and supplied Merlin/Hermes/CACE bundles. It is a project-focused synthesis, not a verbatim archive of every prior chat. Treat explicit status labels and test evidence as authoritative; aspirational goals are not completed capabilities.

## Product objective

Build Merlin as a local-first, modular intelligence workbench that coordinates specialized agents and tools for research, coding, mathematics, visual engineering, CAD, wiring, biochemistry, evolution, and governed recursive self-improvement (RSI). Merlin should eventually use itself to research, test, and improve its own implementation, but it must not approve its own changes or expand its own authority.

Core principle: **capability grows; authority never expands automatically.**

## System topology

- **Merlin Workbench:** user-facing orchestration, project memory, voice prompt, council, ideonomy, evidence ledger, multimodal workspace and plan updates.
- **Expert Robot:** execution/runtime, repository operations, model serving, bounded tool broker, sandbox and verification.
- **Hermes Agent:** optional agent runtime and coding/research worker, operating behind Expert Robot's tool broker and explicit approvals.
- **CACE:** typed capability contracts, formal methods, graph/geometry models, policy enforcement, Lean verification and qualification.
- **Research Miner / Hermes Research Gates:** source collection, evidence records, provenance, reproducibility and research qualification.
- **Specialist engines:** image/video generation, CAD, wiring/netlist, biochemical simulation and evolutionary optimization.
- **Council:** Systems Architect, Skeptical Scientist, Mathematician/Formal Methods Reviewer, Builder/Implementation Lead. Responses should be distinct, evidence-aware and played sequentially using local TTS when available.

## Existing repository and infrastructure

- Primary Expert Robot repository: Mannyspiro/expert-robot.
- CACE app: morganaspim/Cace-app; CACE web app: morganaspim/Cace-ksee-webapp.
- Older related repository: Mannyspiro/refactored-fishstick.
- Preferred compute: Avrea self-hosted runner avrea-ubuntu-latest-8-vcpu.
- Fallback compute: OCI runner cace-oci-a1.
- Avoid paid hosted services, card trials, unnecessary cloud model hosting and repeated heavyweight downloads.
- GitHub Actions minutes have previously been constrained; use Avrea/OCI where possible and avoid redundant CI jobs.
- Observed Avrea runner in the NousCoder acquisition job: 8 vCPU label, approximately 29 GiB RAM and 233 GiB free disk. Re-check on every run rather than treating these as permanent hardware guarantees.
- Never commit model weights, API credentials, runner credentials, or local caches. Model assets belong in ignored model/cache directories with hashes and source provenance.

## Current implementation — 2026-11-02

### Merlin Workbench MVP 0.3

A loopback-only Python standard-library API is now in the Expert Robot branch at `python/merlin/app.py`. It exposes health/capabilities, ideonomy ranking, analogy validation, RSI qualification, geometry validation, netlist validation, metadata-only SQLite event history, and loopback proxy routes for Kokoro speech and a local model. The model route fails closed until `MERLIN_MODEL_QUALIFIED=1`; raw prompt/request text is not written to the event ledger. Dedicated API tests are included in Avrea CI.

### Earlier Merlin Workbench MVP 0.2

Implemented in the separately delivered Merlin MVP package:
- Python standard-library HTTP server and SQLite persistence.
- OpenAI-compatible model gateway, ideonomy endpoint and four-role council.
- Voice prompt capture can automatically convene the council in supported browsers.
- Council responses play sequentially.
- Same-origin voice proxy to local Kokoro TTS; browser speech is fallback.
- Local project/event/idea persistence and honest provider-not-configured behavior.

Local tests: 3 Merlin tests and 10 preserved Research Miner v19 tests passed; Python compilation and browser JavaScript syntax checks passed. A local HTTP smoke verified status and the expected TTS-unavailable response when no TTS sidecar was running.

### Expert Robot PR #67

Development branch: feat/merlin-hermes-kokoro-integration-20261102.

Added:
- Hermes Agent source checkout script, source placed under .tools/hermes-agent.
- NousCoder-14B Q4_K_M GGUF downloader and local llama.cpp server launcher.
- Kokoro-82M ONNX local TTS server, /health, and OpenAI-compatible /v1/audio/speech.
- Model registry, setup documentation, licensing notes and unit tests.
- Existing Avrea CI lane now runs shell syntax and TTS contract tests.
- Avrea live Kokoro workflow downloads/caches the model and voice assets, synthesizes real speech, validates WAV output and uploads a short-lived voice artifact.

Verified:
- Avrea live Kokoro synthesis passed; generated audio artifact was published.
- Expert Robot C++ build and test suite passed.
- Existing policy, regression, benchmark, formal-dependency, CACE return bridge and collar checks passed on the tested PR merge ref.
- Hermes/voice shell and Python contract step passed on the tested PR merge ref.

Verified since the first handoff:
- Hermes Agent source checkout completed on Avrea at revision `5e7c2b254d414e4e25105231f818f385fee67469`.
- NousCoder-14B Q4_K_M download completed on Avrea: 9,001,754,752 bytes; SHA-256 matched the published digest; manifest artifact published.
- Kokoro live synthesis completed successfully again on Avrea.

Still not qualified:
- NousCoder-14B real inference. The first llama.cpp CPU build succeeded, but the smoke response had empty `content`; a follow-up now disables Qwen3 thinking mode and preserves raw diagnostics.
- NousCoder benchmark against existing Qwen3-Coder.
- Full end-to-end council playback in multiple browsers.
- OCI runner execution for this iteration.

## Model and voice decisions

### Coding

- Keep existing Qwen/Qwen3-Coder-30B-A3B-Instruct role unchanged.
- Add NousCoder-14B as a candidate specialist, not a default replacement.
- Candidate source: NousResearch/NousCoder-14B.
- Quantized artifact: bartowski/NousResearch_NousCoder-14B-GGUF.
- Default file: NousResearch_NousCoder-14B-Q4_K_M.gguf (~9 GB).
- Published SHA-256: 9cc51afc755319db42a6324baf3395436cce5954dc87df95d3b9e7d625610624.
- Model weights license: Apache-2.0.
- Serve via llama.cpp with 65,536 context for Hermes compatibility. Keep host loopback by default.
- Do not promote based on successful download alone. Use fixed held-out coding tasks, correctness checks, tool discipline, latency, memory and cost.

### Hermes Agent

- Upstream: NousResearch/hermes-agent, MIT license.
- Clone to .tools/hermes-agent, record exact upstream commit in provenance.
- Source-only download by default; optional user-level install is explicit.
- Current Hermes Agent quickstart documents 64K context minimum.
- Hermes must inherit Expert Robot sandbox/tool-broker permissions; no direct credential access, unrestricted shell, deployment or self-promotion authority.

### Voice

- Engine: Kokoro-82M ONNX.
- ONNX runtime MIT; model weights Apache-2.0.
- Generated speech does not require a credit line under these listed licenses; retain license/notice material and recheck voice-pack/data terms before redistribution.
- Initial languages: English US/UK; WAV output.
- Local service default: 127.0.0.1:8880; Merlin proxies same-origin.
- Council voices play sequentially, with Stop support and browser TTS fallback.

## CACE technical architecture

CACE is the typed source of truth; avoid a second duplicated JavaScript capability engine.

Required contracts and interfaces:
- Typed /api and capability registry.
- client.ts, types.ts, config.ts, errors.ts.
- /api/capabilities and /api/graphs/validate.
- capability_policy_hash and registry_contract_hash.
- No-internet sandbox, leases, idempotency, preview diff + approval, commit-hash verification and heartbeats.
- Module graphs, coordinate systems, animated graphs, optional GPU paths and local no-code AI.
- Preserve structured JSON block separation conventions.
- Geometry, graph and coordinate transforms must be explicit and unit-aware.

RSI gates:
- Compare information gain against compute/time cost, variance and diminishing returns.
- Candidate work occurs in isolated branches/sandboxes.
- Promotion requires reproducible tests, independent verification, held-out qualification, rollback, authority non-expansion, collar/security checks and explicit human approval.
- A failed gate remains visible; never relabel a hypothesis or simulation as a verified result.

## Outstanding formal research tasks

Latest recorded UFT residuals:
1. Recover complete THTG action and source equations.
2. Correct the Page-curve derivation and establish its finite maximum.
3. Resolve 5D coupling dimensions and curvature-invariant basis.
4. Derive/recover exact beta functions and independently reproduce the proposed fixed point.
5. Formalize conditional theorems in Lean with explicit assumptions and axiom-dependency audit.

Other earlier research tracks include numerical FRG confirmation, lattice Page curve, SM-shifted fixed-point coordinates, cosmological MCMC and Lean encoding. These remain open unless a later reproducible artifact proves otherwise.

## Research intelligence and inductive engineering

**Implemented in this branch:** deterministic evidence ledger with hashed-artifact promotion requirements; ideonomy ranking that rejects candidates without mechanisms, assumptions, constraints, observables and falsifiers; explicit analogy mapping that requires preserved invariants and boundary conditions; and a fail-closed RSI candidate gate. Dedicated unit tests run in Avrea CI. These are candidate-generation and governance primitives, not an autonomous scientific discovery engine.

**Bundle intake finding:** the supplied Hermes Research Gates v16 package reports 541 passed / 2 skipped, while excluding nine inherited modules. An independent local collection attempt against the included `merlin_v11/MERLIN` source stopped at test collection because `merlin.vendor.cace_engine_v5` was missing. Therefore the package-level 541-pass claim is retained as a supplied report, not independently reproduced from the provided archive. Exact-head Lean qualification and live Hermes/browser verification remain open.

## Visual engineering and mathematical visualization

**Implemented foundation in this branch:** typed geometry IR with unit conversion, face/topology checks, closed-solid manifold checks, bounding boxes and OpenSCAD export; typed wiring/netlist IR with pin identity, duplicate-net detection, supply-ground short checks and declared voltage/current rating preflight. Dedicated unit tests are added to Avrea CI. These are structural preflight tools, not production CAD, circuit simulation, DRC/LVS, or electrical safety qualification.

Use one typed geometry/constraint representation for generated images, 3D CAD, technical drafting and wiring/netlist outputs:
- dimensions, units, coordinate frames, materials, constraints, connection topology and revision hashes.
- Export SVG, OpenSCAD/mesh and JSON where appropriate.
- CAD geometry is not qualified by a pretty rendering; require constraint, dimensional and topology checks.
- Wiring requires netlist, electrical-rule checks, voltage/current/power ratings, insulation/clearance rules and qualified human review.
- Multi-scale graph/symmetry visualization from the supplied 3×3 image is a UI motif, not evidence of a universal physical law.

## Biochemistry, evolution and research

- Start with curated licensed datasets, unit-aware models, explicit assumptions and uncertainty.
- Build reaction kinetics, regulatory networks and evolutionary simulations with reference benchmarks.
- No wet-lab actuation or clinical claims from unvalidated models.
- Research Miner v19 remains a separate integration candidate; its README labels its Poisson, TMz FDTD and thermal kernels as teaching baselines, not production TCAD/foundry-ready tools.
- Research Gates v16 report records 541 passed / 2 skipped but excludes nine inherited modules; exact-head Lean qualification, live Hermes/browser validation and some Maxwell qualification were still pending in that report.
- Preserve citations, source revision, retrieval time, hashes, license rights and reproducibility metadata.

## Ideonomy and problem reframing

Candidate pipeline:
1. Generate diverse ideas across relevant fields.
2. State mechanism, assumptions, constraints and causal path.
3. Reject incoherent, undefined or physically impossible proposals.
4. Rank surviving ideas by transparent criteria, including novelty, feasibility, evidence and testability.
5. Propose falsifiable experiments or simulations.
6. Keep outcomes and failed hypotheses in the evidence ledger.

Problem reframing protocol:
1. Define the original problem and its invariants.
2. Map it to a simpler, established problem.
3. List entities, operations, invariants, boundary conditions and failure modes in both domains.
4. Prove or test that the mapping preserves the relevant invariants.
5. Solve the simpler problem and translate back.
6. Test against the original problem; reject analogies that do not preserve essential properties.

## Next milestones

1. Finish NousCoder acquisition and SHA-256 verification on Avrea; record the model cache/provenance. If acquisition fails, diagnose exact cause and do not claim the model is downloaded.
2. Complete Hermes Agent source checkout and record its commit.
3. Start llama.cpp and test a small real coding prompt; compare against Qwen3-Coder on held-out tasks.
4. Wire Merlin Workbench to Expert Robot's model and TTS adapters through stable typed contracts.
5. Add evidence provenance and malformed-response tests to the workbench.
6. Import Research Miner v19 behind a versioned adapter and preserve its limitations.
7. Add CACE/Lean qualification endpoints and verify against pinned toolchain/commit.
8. Implement shared geometry and electrical-netlist IR before CAD/wiring generation.
9. Add image/video adapters with rights, cost and provenance metadata.
10. Build biochemical/evolutionary simulation modules with unit-aware benchmarks.
11. Add isolated RSI candidate runs, compute budgets, held-out evaluations and manual promotion.

## Operational rule

At each iteration append: observed requirement → source/evidence → failure/gap → smallest testable subproblem → acceptance test → result → plan update. Never claim a feature is complete merely because its UI or installer exists.


## Network-native streamed inference update — 2026-11-02

New user requirement: make Merlin fast by networking to remote AI models rather than requiring model weights to run locally. The chosen design streams inference output over HTTPS; it does not stream/download model weights for each request.

Implemented on this branch:
- POST /api/chat can route to an OpenAI-compatible HTTPS endpoint using runtime-only MERLIN_REMOTE_MODEL_URL, MERLIN_REMOTE_API_KEY, and MERLIN_REMOTE_ALLOWED_HOSTS.
- Remote route requires a separate MERLIN_REMOTE_MODEL_QUALIFIED=1 gate.
- Exact hostname allowlisting and HTTPS validation are enforced.
- stream: true passes through upstream SSE incrementally; non-stream JSON is preserved.
- Local llama.cpp remains separate and gated by MERLIN_MODEL_QUALIFIED=1.
- Added endpoint validation tests, mocked SSE passthrough test, example environment contract and docs/NETWORK_MODEL_STREAMING_V1.md.
- Updated docs/ENGINEERING_PLAN_V17.md with inductive v18 requirements and docs/merlin-mvp-api.md.

Not yet done:
- Avrea CI for the newest stream implementation is pending; do not claim the new gateway tests have passed until its run is green.
- No real provider credentials have been configured or used; remote inference has not been exercised against a paid or free external model endpoint.
- No provider benchmark, multi-provider role router, production async connection pool, cancellation telemetry or council fan-out is implemented yet.
- Do not set the remote qualification flag until the chosen provider/model is tested and its privacy/retention settings are reviewed.
- The current Python standard-library HTTP server is a low-concurrency MVP, not the final high-throughput gateway.

Performance roadmap:
1. Verify SSE chunks arrive incrementally with Avrea CI.
2. Build an async connection-pooled gateway with cancellation, bounded concurrency and deadlines.
3. Add task-role/provider registry and explicit model selection.
4. Measure TTFT, tokens/sec, end-to-end latency, error rate and cost per successful task on held-out tasks.
5. Add council parallel review and streamed Kokoro audio playback.
6. Keep Avrea/OCI for private work, code execution, simulation and explicitly authorized local fallback.

Trust rule: never silently move private prompts to a different provider during fallback. Credentials stay in runtime secrets; prompts are not written to event logs. Connectivity is not model qualification.


## Hybrid compressed intelligence research update — 2026-11-02

Added docs/HYBRID_COMPRESSED_INTELLIGENCE_V1.md and engineering plan v19.

Key decision: hybrid local + remote. Keep a small quantized local generalist resident; hot-swap specialist models at task boundaries; swap LoRA adapters, context packs, retrieval data and tools separately; use remote experts when local capability is inadequate. Do not stream model weights per request.

Source shortlist:
- llama.cpp: GGUF quantization, mmap/lazy loading, KV cache types and CPU/GPU offload.
- llama-swap: model process hot-swapping across compatible local inference servers.
- LLM Compressor: calibration-aware weight/activation/KV compression and sequential offload where supported.
- NASA NPO-51334-1: NASA catalog marks this vision/spacecraft pose CNN software Open Source; it includes TensorFlow model compression and image augmentation. It is not a general LLM compressor.
- Patent US12375101B1 is assigned to Atombeam Technologies Inc., not NASA. It describes distributed adaptive compression; not code and not a free patent license. No directly relevant NASA-owned patent verified in this research pass.

License rule: no stripping attribution, copyright notices, license texts or NOTICE files. "Free of charge" is not identical to unrestricted release. Select only NASA Open Source/General Public Release entries whose actual terms allow the use. Patent publication does not grant rights to practice claims.

Parrondo principle: treat A=fast local model, B=remote/specialist model, and adaptive switching/council as hypotheses. Measure on held-out tasks with equal budgets; hybrid only wins if net quality after latency, cost, privacy and error penalties beats fixed A and B. Verbose council debate belongs in a transcript; voice playback should start with the lead answer and queue optional council contributions.

Status: architecture/design only. No new quantized model, NASA source, llama-swap or LLM Compressor has been downloaded or integrated. Hardware inventory and local-vs-remote benchmarks remain outstanding. The previous core Avrea CI and remote gateway tests passed; the separate NousCoder inference qualification was still running at the last checked status. The current gateway remains the production candidate until the hot-swap prototype passes its own gates.
