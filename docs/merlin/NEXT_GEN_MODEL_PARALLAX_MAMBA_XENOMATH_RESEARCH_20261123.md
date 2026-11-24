# Merlin next-generation model and simulated-computing research program
**Status:** exploratory design and reproducible scalar math, not a trained model, model-architecture improvement, full formal proof, physical hardware emulation, or production deployment. Recorded 2026-11-23 UTC. This is a child of canonical Merlin master plan v6; do not rewrite or close its ten tracks.

## Question / preregistered frame
Can multiple small specialists, a recurrent state-space backbone, selective higher-order attention, and a simulated-physics computational carrier improve Merlin's **matched-quality** correctness/latency/RAM/cost over its existing llama.cpp baseline?

**Observable target:** same held-out instruction, state tracking, retrieval, coding, mathematics and visual/engineering benchmark outputs with quality floor frozen before testing; report median and tail latency (ms/token and total), max RSS and VRAM (MiB), model+KV disk footprint (GiB), host energy (J where measured), peak build/inference resource use, retrieval/proof correctness and exact runner/weights/hardware identities. Count routing/model-loading, simulator orchestration, external-tool and verification overhead. Separate cold start and warm cache. The comparison must use the same licensed weights or clearly label non-comparable architectures and training budgets.

**Competing mechanisms:** (A) current quantized local decoder; (B) selective Mamba-3 state-space backbone; (C) Parallax-style local linear-estimate attention layers; (D) hybrid with a recurrent backbone, occasional local/Parallax-like attention and small domain-specialist models; (E) entirely simulated computational carrier whose virtual rules support a useful mapping back to host-executable algorithms; (F) simple retrieval and tool-use improvements with no architectural change. Do not confer special credibility on D or E because they are novel.

**Falsifiers:** any claimed advantage disappears once total host overhead, output correctness, calibration, comparable hardware, or long-context state tracking is controlled; any simulation result fails to map to the desired task; or the stated state bound / composition invariant has a counterexample.

## Published sources, exact code identities
- *Mamba-3: Improved Sequence Modeling using State Space Principles*, Lahoti et al., ICLR 2026; https://arxiv.org/abs/2603.15569. Paper reports half-state-size parity with Mamba-2 on measured perplexity configurations and better measured state tracking/retrieval. Official code: https://github.com/state-spaces/mamba pinned at `e9594ce1c732d97440f0332fdc43170a2294dbfa` (2026-07-22). The publication's experiments are not Merlin measurements.
- *Parallax: Parameterized Local Linear Attention for Language Modeling*, Zuo et al., 2026; https://arxiv.org/abs/2605.29157. Official MIT code: https://github.com/Yifei-Zuo/Parallax pinned at `987102538da4c831a0b6f2dde03ce3251182a7cf` (2026-07-07). **Not** linear-complexity attention, still uses KV caching; the authors report gains in compared settings. Code not vendored.
- *The Hyperscale Lottery: How State-Space Models Have Sacrificed Edge Efficiency*, Geens et al., 2026; https://arxiv.org/abs/2604.07935. Contradictory/important edge evidence: an architecture designed for hyperscale GPUs may hurt single-user latency on edge hardware. This is a reported result, not an independently replicated Merlin measurement.

## Model routing hypotheses
1. Low-latency conversational/controller model (small quantized model). Use existing bounded model protocol, never give model authority over tool permissions.
2. Mathematical / science specialist, with independently checked symbolic/numeric algorithms and proofs; hallucinated proofs remain unverified.
3. Coding / formal methods specialist. Return executable tests, diffs and source identity, not automatic merges.
4. Vision / CAD critic and visual model when an operator explicitly provides image/design data. Keep graphics safety, source and unit checks.
5. Retrieval/Second Brain service with exact source citations; do not train on private user vaults without explicit consent and data policy.
6. Independent verifier(s) that differ in method/input sources, not merely two LLMs echoing each other's arguments.

Use small models only when measured cost/quality improves the task; avoid keeping six idle models in RAM. CPU/offload and disk page behavior matter on hardware with limited RAM. No automatic weight mutation has been implemented.

## Simulated physics as a computational substrate
A virtual physics environment can be **the actual algorithm**. No physical equivalent is required. The correct experiment measures the result on host hardware, not fidelity to ordinary physical laws. Let a virtual substrate have carrier state `S`, deterministic update `F`, readout `G` and host interpreter cost `C(F,S)`. For target function `T` and input `x`, require readout `G(F^k(S_0,x))` agree with `T(x)` within a declared tolerance. Measure *all* host work to execute `F` and `G`, including encoding/decoding, state preparation and verifier.

### Mathematical reference 1 (derived, not claimed novel)
For signal `x_0,…,x_t` and `0 ≤ a ≤ 1`, define `s_{-1}=0`, `s_t=a s_{t-1}+(1-a)x_t`. By induction,
`s_t=(1-a)Σ_{j=0}^t a^{t-j} x_j` in exact real arithmetic.
If `|x_j| ≤ B`, then `|s_t|≤ B`: the update is a convex combination of values already in `[-B,B]` including initial zero. Perturbing every input by at most `ε` perturbs every state by at most `ε` using the same convexity argument.
The direct reference needs `O(t)` work per output, `O(n²)` total for all outputs; the recurrence has `O(n)` arithmetic and `O(1)` working state apart from output storage. This is a classical exponentially weighted recurrence, **not** a new Parallax/Mamba kernel or novelty proof.
In `python/merlin/simulated_parallax_models.py`, a virtual second channel computes truncated local history `ℓ_t`, then `h_t=(1-λ)s_t+λℓ_t` for `λ∈[0,1]`. This satisfies convex bounds while exposing a controlled accuracy/performance tradeoff. Its weights and windows are hand-set, not learned. Timings from Python on synthetic signals are not training/inference/device/energy benchmarks.

### Paradoxes and xenomathematics
A contradiction must be localized before attempting a new mathematical language. Record which propositions cannot simultaneously hold, whether quantifiers, units, time, carrier dimension or boundary/gluing conditions differ; test with a small countermodel. Apply:
- **Continuum:** specify carrier, topology, domain, boundary data, discretization, error estimate and refinement. An affine interpolation failure does not imply absence of all continuous extensions.
- **N-ality:** separate spatial dimensions, independent state variables, logical channels, and timescales. An n-way diagram is not automatically a new physical interaction.
- **Simplex:** enforce `λ_i ≥ 0`, `Σλ_i=1`, compatible units, and whether vertices are affinely independent. Do not soften hard security gates with weights.
- **Glyphs:** treat pictorial/symbolic syntax as a typed IR. State parse/typing rules and a semantics-preserving translation to arithmetic, code or a proof checker before claiming power.
- **Fuzzy/continuum logic:** define membership versus probability and inspect which contradiction rules are retained. A graded-truth interpretation does not make a classical inconsistency disappear by fiat.
- **Invented xenomaths:** declare new axioms and operations, show at least one formal model or countermodel and establish whether derived claims differ from an isomorphic known system. Novelty remains unknown until reviewed literature/proof search.

## Ranked loop and subloop program
1. **P0 scientific integrity:** every worker/Studio prompt receives immutable skeptical-scientist guidance; code-level type gates and tests must support it. Record actual bias trigger, competing mechanism, falsifier, independent checker and negative results. Prompt injection cannot expand the capability allowlist.
2. **P1 bounded state machine:** per-run task count, depth, fanout and step ceilings. Parent and child protocols have immutable IDs and exact parents. Independent verification precedes child admission; snapshots have checksums; a host-scheduled invoker can resume after restart. These are workflow guarantees only; a digest is not an authenticated signature.
3. **P2 simulated reference:** run the scalar recurrence, truncated window and two-channel model with fixed seeds and increasing sequence lengths; measure host CPU time and numerical error, then check reference invariants. Use repeated trials and confidence intervals before ranking.
4. **P3 Mamba/Parallax comparison:** review pinned upstream licenses/toolchains, then run matched real workloads on feasible offline hardware with exact model training/weight and numerical precision controls. Incorporate edge-latency counterevidence. No automatic vendor code or binaries.
5. **P4 architecture candidate:** compare baseline against narrow hybrid and routed-specialist versions after quality and resource evidence. Keep null results and ablations.
6. **P5 release review:** independent security, source/licensing, reproducibility, hardware, privacy, UI and human promotion gates before changing production.

**Research loop reality:** the new `ResearchSubloops` class is resumable and bounded, but it does **not** run itself in the background. A configured local daemon, OCI service or scheduled CI worker with explicit resource and network policy is still required to invoke experiments on a recurring basis. No model self-training, unrestricted tool rights or unattended production merges were enabled.

**Source/evidence limits:** read published paper abstracts and pinned Git metadata, selected existing Merlin source and historical test evidence. No original Mamba-3 or Parallax GPU benchmark run or own local model-weights task performed here. A proved identity about a scalar toy model is not a claimed proof of an improved language model.
