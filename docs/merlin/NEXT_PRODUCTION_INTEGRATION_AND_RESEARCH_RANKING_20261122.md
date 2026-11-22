# Merlin production integration and research ranking — 2026-11-22

Status: engineering design/checkpoint, **not** merged, deployed, licensed for distribution, or production qualified. Evidence classes are distinguished below. This is additive to the canonical master plan, not a replacement.

## Exact-source evidence ledger

- CACE draft PR #121 at `18f2227db178e375485102f5fdd61f5bd9f63dc3`: private OCI ARM64 ZIP acceptance [#45058283924](https://github.com/morganaspim/Cace-app/actions/runs/45058283924) passed packaged Python, extracted Studio UI and conversation restart, separate real GGUF inference and private cleanup. **These were separate tests; a true Studio-to-bundled-model conversation has not yet been admitted.**
- CACE subsequent contract source `12f3bfb5548098e1d0603e11ab91af881019c7a8`, synthetic exact-source [#45067060547](https://github.com/morganaspim/Cace-app/actions/runs/45067060547): 13/13 Studio helper tests pass, including explicit model startup configuration, chat endpoint and persisted-response evidence oracle. **Synthetic only**.
- expert-robot draft PR #205 at `aa13238eff42a26f060046becfa910603bec5ff4`: source evidence for Titan state-model and structural test vectors, Engineering IR/netlist/OpenSCAD and bounded Ideonomy mathematics. No claim that these domains are integrated into the Studio packaged runtime.
- Native model tool-selection exact output remains unqualified; separately approved real-model quality and browser service gates remain open. Base integrated review PR #204 and overlapping drafts are not automatically merged.

## Highest-ranked production prerequisites

1. **P0 — One real Studio-to-bundled-GGUF conversation**, using an extracted exact verified ZIP in a disposable unprivileged namespace. Send one exact-reference prompt via `POST /api/chat`, poll `GET /api/runs/<id>`, read the same durable conversation, verify one genuine `model_request` event and independent exact output; record only typed hashes and counts, enforce time/memory/process limits and cleanup. Reject synthetic fakes as final evidence. Preserve failure. Keep production_qualified=false.
2. **P0 — Release correctness and supply chain.** Independent PR overlap/provenance/secret review; signed and reproducible build, runtime ABI and security review, component/model redistribution rights, recovery, cancellation, rollback and explicit release approval. No model weights in CI artifacts.
3. **P1 — Browser and agent runtime.** Reconcile root-owned stale browser socket/service status read-only before any separately authorized install; browser-native public-source capture/restart and model-selected tool workflows. Preserve prompt-injection and private-network deny tests.
4. **P1 — RAM/compute profile harness.** Benchmark the same exact real tasks with hardware, model hash, quantization, context, KV-cache type, batch, throughput, latency, peak RSS/VRAM, joules (if measurable), output accuracy and budget. Explore llama.cpp quantization/KV cache/batched scheduling/model eviction, never infer efficiency from an unmeasured algorithmic analogy.
5. **P2 — Local speech.** Evaluate whisper.cpp STT, Piper-style TTS and optional voice interruption as **separate opt-in local worker**. Confirm input/output audio handling and privacy boundaries, real device smoke, resource caps and packaging license review.
6. **P2 — Creative pipeline.** Evaluate ComfyUI as a separate localhost graph worker rather than embedding its licensed code into Merlin. First tasks: controlled render, anatomy reference labeling (not diagnosis), clothing/material variants, cinematic look, reproducible seed, metadata, output hashes and approval-gated file outputs. Image generation is not a CAD or measurement oracle. Respect per-model licenses and memory budgets.
7. **P2 — Engineering CAD/EDA.** Reuse existing Engineering IR -> SPICE netlist and OpenSCAD preview. Evaluate KiCad scripting and ngspice separately with pin/net identity, electrical-rule checks, simulation oracle, source/geometry manifests and visual inspection. Do not confuse simulated ideal DC with physically verified device safety.
8. **P3 — Scientific exploration, parallax and advanced architecture.** Sandbox alternative mathematical representations and hypothetical physical effects in explicit numerical models; contrast ordinary optics, sensor parallax and electromagnetic models against new hypotheses. Require dimensioned premises, controls, conservation laws, predictions, uncertainty, parameter sweeps and falsifiers before escalating.

## Titan, mathematics and design lenses

Titan is a **protocol-lifecycle research model, not a deployed cipher**. Its `titan_crypto_lab.py` explicitly performs no cryptography; `titan_protocol_model.py` supplies structural envelopes and synthetic vectors, not encryption/decryption known-answer tests. Use vetted cryptographic implementations and standards. ML-KEM is standardized in NIST FIPS 203 (2024; review published errata), with hybrid key agreement requiring an independently reviewed composition. Do not combine custom Go-board rotor/lattice states with production key derivation, nonces or authentication.

The existing `python/dot_ai_os/math_lenses.py` includes normalized simplex weights, convex blending, n-ality signatures, continuum interpolation and fuzzy membership; `python/merlin/ideonomy.py` supports bounded candidate search. Rank applied mathematics by task value:

1. **Sparse linear algebra, dimensional analysis, numerical conditioning and constraint programming** for EDA/CAD, simulation and compute budgeting; check against established numerical solvers.
2. **Simplex/barycentric coordinates** for geometry, mesh interpolation, mixtures and multi-objective constrained evaluation; verify weights sum to one and nonnegativity as applicable.
3. **n-ality typed relation axes, graph/hypergraph and information geometry** for multiple interacting systems; map back to concrete relationships and compare with standard relational/graph baselines.
4. **Interval arithmetic, uncertainty propagation and validated numerics** to prevent false precision in simulation and architecture selection.
5. **Fuzzy logic** for preference ranking only, not permissions, verification or authentication.
6. **Glyph/symbolic representations, xenomaths and Ideonomy lacuna searches** as speculative representations with explicitly tested encodings and translation-back losses. Do not assert novelty from missing catalogue entries.
7. **Parallax/alien-science virtual experiments** in standard optical/electromagnetic simulators with controlled altered assumptions; report simulator-only output, never new physical capability without physical evidence.

Lenses for this gate: simplex=deferred (no geometry in chat transaction); n-ality=applied to independent dimensions {runtime, data, security, provenance, model quality}; continuum=applied to latency/memory budgets; fuzzy=not applicable to Boolean release gates. None may soften production authorization or trust boundaries.

## External reference projects to evaluate, not vendor silently

- [llama.cpp](https://github.com/ggml-org/llama.cpp) — existing exact-pinned local runtime; investigate compatible quantization/KV/cache benchmarks.
- [ComfyUI](https://github.com/Comfy-Org/ComfyUI) — modular graph image/video/3D API, GPL-3.0; isolate process and review both code and model licenses before distribution.
- [whisper.cpp](https://github.com/ggml-org/whisper.cpp) and [Piper](https://github.com/rhasspy/piper) — offline voice design candidates; confirm maintained forks and license/model terms.
- [KiCad](https://gitlab.com/kicad/code/kicad), [ngspice](https://ngspice.sourceforge.io/), [OpenSCAD](https://github.com/openscad/openscad) — schematics, simulation and mechanical geometry candidates; verify compatibility and license.
- [OpenField](https://github.com/wexloops/openfield) — example of cinematic control / image-to-video on ComfyUI, not independently qualified.

## Decision and falsifier

Do not expand the ZIP with GPU-heavy visual and speech weights before acceptance of core chat, provenance and target-hardware memory/latency. A green isolated GGUF math request does not establish quality of model-selected tools, CAD, anatomy or physics. Smallest discriminating next experiment: live chat through Studio in same isolated package, with independent reference `6*7=42`, durable answer, bounded response hash, failure receipts and cleanup.

Parent roadmap: existing Merlin master plan v6 and its additive dated updates. This document adds prioritization and does not mutate their recorded task statuses.
