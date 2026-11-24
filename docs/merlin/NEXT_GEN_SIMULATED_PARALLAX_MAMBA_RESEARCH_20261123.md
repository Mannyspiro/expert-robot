# Merlin lightweight model architecture / simulated-substrate research — 2026-11-23

**Evidence class:** literature-grounded proposal + deterministic Python mathematical experiment. This branch **does not** implement Mamba-3, Parallax, an LLM training run, a theorem prover or an always-running agent. No weights, model routing, hardware or production release changed.

## Research question and competing hypotheses

Can Merlin combine (1) recurrent state compression, (2) selectively deployed higher-quality attention, (3) specialized small local models and (4) explicit user-reviewed Second Brain memory to improve useful end-to-end quality, resident memory and total inference costs on **Merlin's actual target hardware**?

The strongest alternatives to beat are the existing local llama.cpp-style model path, using the same permitted weights, precision, task set, token budgets, data and host, plus the single model without any new routing, simulator or graph overhead. Compare *total* wall time, CPU/GPU memory, power if instrumented, accuracy, tool-use success and citation correctness. A lower asymptotic complexity is not necessarily a lower end-to-end latency.

## Primary-source ledger

| Research | Exact source / evidence | Transfer and important disanalogy |
| --- | --- | --- |
| Parallax (2026), Parameterized Local Linear Attention | [arXiv 2605.29157](https://arxiv.org/abs/2605.29157); [MIT-licensed implementation pinned at `987102538da4c831a0b6f2dde03ce3251182a7cf`](https://github.com/Yifei-Zuo/Parallax/tree/987102538da4c831a0b6f2dde03ce3251182a7cf) | Local linear regression correction for attention; **not** linear-complexity attention, still requires KV cache. Reported better perplexity at 0.6B/1.7B matched configurations. No evidence yet that Merlin's local host benefits. |
| Mamba-3 (ICLR 2026) | [ICLR abstract](https://proceedings.iclr.cc/paper_files/paper/2026/hash/8abd2043b71a074278d5f687947bff9c-Abstract-Conference.html); [Mamba implementation pinned at `e9594ce1c732d97440f0332fdc43170a2294dbfa`](https://github.com/state-spaces/mamba/tree/e9594ce1c732d97440f0332fdc43170a2294dbfa) | Complex-valued state updates and multi-input/multi-output SSMs suggest efficient state tracking. Published gains are measured at particular model scales; they do not imply equal gains on CPU/edge and local Merlin workloads. |
| Counterevidence: edge efficiency | [Hyperscale Lottery, arXiv 2604.07935](https://arxiv.org/abs/2604.07935) | Reports measurable Mamba-3 edge latency penalties in its evaluated cases. Prevents automatically ranking Mamba-3 highest solely on GPU-scale benchmarks. |
| Titans (NeurIPS 2025) | [Conference abstract](https://papers.neurips.cc/paper_files/paper/2025/hash/a4ca07aa108036f80cbb5b82285fd4b1-Abstract-Conference.html) | Test-time memory is an optional model mechanism, not a reason to train on private vaults or convert notes to factual truth. |

## Mathematical reference experiment (not a new theorem)

For fixed (a\in[0,1]), let (s_{-1}=0) and (s_t=a s_{t-1}+(1-a)x_t). Induction gives:

[
s_t=(1-a)\sum_{j=0}^t a^{t-j}x_j.
]

If every (|x_j|\le B), then (|s_t|\le B) by convexity (base state zero, (a\in[0,1])). This is an ordinary, established recurrence identity, **not novel xenomaths**. Its scalar recurrent representation computes the same ideal-arithmetic output in (O(n)) work and (O(1)) recurrent state rather than directly summing the whole history for every step in (O(n^2)) work. Python's floating-point rounding creates bounded observed differences; computational optimization follows from recasting the problem, not making virtual hardware physically real.

The `simulated_two_channel` toy candidate evaluates ((1-\lambda)s_t+\lambda l_t) with (lambda\in[0,1]) and (l_t) a sliding-window approximation. This is a **simplex mixture of two simulated channels**, not Parallax implementation. An n-ality record must separately describe state dimension, logical channels, geometry and time. Glyphs may provide typed syntax but gain mathematical significance only if semantics and inversion tests are explicit.

## Why a simulated world can give real benefits

No requirement exists that a software world mirror experimentally realized physics. A simulator may act as a computational representation or optimization search space. Evaluate its *measured useful host computation*: same specified input/output semantics, matched error budget, total CPU/GPU runtime, RAM, numerical accuracy and overhead including state preparation, simulation, translation back and verification. If the simulated substrate generates correct useful predictions at lower cost, that gain is real **within its declared workload**. Its fictional geometry alone does not imply a silicon speedup or a new physical law.

## Paradox classification protocol

1. Pin each proposition's axioms, quantifiers, reference frame, time and meaning of “true,” “continuous,” “possible,” and “computationally equivalent.”
2. Search for an actual formal contradiction under the **same** theory; otherwise classify as scope equivocation, model mismatch, incompatible boundary constraints, self-reference, insufficient measurement or unresolved.
3. Consider continuum representation only with carrier, domain, gluing/boundary conditions, discretization and refinement test. Affine-extension failure need not imply failure of all continuous extensions.
4. Consider normalized simplex and independent n-ality axes only when they preserve relevant invariants. A visualization or multi-valued truth assignment does not itself prove a paradox resolved.
5. For a candidate glyph calculus or xenomaths, define grammar, carrier, operations, axioms, interpretations, countermodels, and a translation-back correctness test. Novelty requires literature search and formal verification, not a new name.
6. Return a falsifiable consequence or **unresolved**, with reasons and counterexamples. Never replace failed evidence with plausibility scores.

## Continuous improvement boundaries

The shared `skeptical_scientist_policy.py` is included in the Studio model system message and in the deterministic worker prompt compiler, with an identical standalone Studio copy. This is **prompt-policy coverage**, not a formal guarantee every model answer is bias-free.

The `bounded_research_loop.py` module provides explicit root tasks, maximum four child branches per step, maximum four recursion levels and 32 steps, independent-check callback, evidence receipts, and snapshot/restore validation. Its caller must be a separately authorized worker. It does not schedule work in the background, run model inference, use paid services or submit code. A SHA checksum detects accidental corruption, **not adversarial tampering by someone who can rewrite the checkpoint and its hash**.

## Ranked experiments and acceptance

1. Finish exact-source native CI, portable ZIP and negative controls. Any regression blocks branch review; do not relax original tests.
2. Run the existing local model on matched retrieval/induction/state tracking/code/CAD questions. Record latency/RSS, tool success, retention and independently graded answers.
3. Deploy a reproducible optional *research* benchmark of Mamba vs attention on actual target CPU/GPU and quantify any model-quality cost with finite resources. Do not route user tasks to an unproven architecture.
4. Investigate Parallax layer in a small fixed-attention prototype, first unit kernels and numerical stability, then training-quality parity with matched budget.
5. Run ideonomy/lacuna enumerations on *declared* finite mechanism/representation dimensions; log searched vs omitted combinations and falsifiers.
6. Introduce a separate reviewable experiment supervisor that resumes checkpointed loops under CPU/RAM/step/budget leases and human authority, only after native host security and crash/replay tests.

**Blocking gates:** no proof of novel mathematics, no formal Lean verification, no production model-weight training, no real Parallax/Mamba inference in this change, no verified physical hardware gains. No merged or deployed autonomy.
