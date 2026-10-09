# OpenAI mathematics proof intake — 2026-10-09

Scope: Expert Robot PR #47, branch `research/magick-ir-v0-1`. This is an **intake and qualification plan**, NOT a claim that the new theorems have compiled in this project or that CACE implements them. Existing collar, CI, verifier, and promotion rules are unchanged.

## Primary sources and provenance

- Announcement (2026-10-06): https://openai.com/index/sharing-ai-progress-in-mathematics/
- Upstream source: https://github.com/openai/math
- Upstream formalization registry: https://github.com/openai/math/blob/main/lean/formalization.yaml
- Upstream comparator instructions: https://github.com/openai/math/blob/main/lean/ComparatorChallenges/README.md
- Upstream license: Apache-2.0, https://github.com/openai/math/blob/main/LICENSE. Individual third-party dependencies retain their own licenses.
- Observed upstream Lean toolchain: `leanprover/lean4:v4.34.1`; observed Mathlib lock rev: `d13f23b723b8a846827a245b89c10fc7d3f11612`. Expert Robot handoff uses Lean/mathlib v4.34.0; do **not** replace its pins opportunistically.
- Source inspection on 2026-10-09. Upstream is moving: the **upstream repository commit must be resolved and pinned** before reproducible compilation or copying any code; recorded blob SHAs below are file identities but not an entire dependency snapshot.
- OpenAI's README says some results are not formalized and some may contain issues. Independent checking and paper-to-statement fidelity are separate tasks.

## Ranked mathematically relevant candidates

| Rank | Formal declaration / source blob SHA | Expected use | Limit / acceptance test |
|---|---|---|---|
| 1 | `OAI.BoundedTreewidthL1.l1Append_norm_sub`; `OAI/Combinatorics/TreewidthL1/Main.lean`; blob `bc8b92a4b0aa73a24be359b4ef8f85448f544b22` | Small compositional L1 norm identity that may be portable to graph-distance features or a CACE path/geometry measurement bridge | First isolate this **leaf lemma** with no OAI custom imports if possible; independently build and audit its statement, mathematical assumptions and axioms. It is not itself a solver certification. |
| 2 | `OAI.ErdosGallai.erdos_gallai`; `OAI/Combinatorics/CycleDecomposition/Main.lean`; blob `a146a6edad4e9c89fcd4358cfb25141fe649c24f` | Graph decomposition concepts for testing cyclic control-flow graph coverage after the bounded DAG guard-cut experiment | Graph existence/cost result is not a proof that every executable path is guarded. Derive an explicit graph extraction/flow safety bridge and test counterexamples. |
| 3 | `OAI.CompleteCrouzeix.main`; `OAI/Analysis/NumericalRange/Main.lean`; blob `efa3c8b2063e4cb282059ec21521635deffcc150` | Complex matrix polynomial norm inequality, potentially a numerical-analysis lemma for matrix functions in CACE | Requires correct translation of finite complex matrices and the numerical range to CACE's operator model. No direct FEM or solver bound follows without a separate proof. |
| 4 | `OAI.UniformSparsestCut.mainGap`; `OAI/Combinatorics/SparsestCut/Main.lean`; blob `ad60be7a89d0c9442500beaa8eaa77127042fabd` | Counterexample inspiration for optimistic graph optimization relaxations | The theorem concerns a uniform sparsest-cut relaxation **not** the min-cost vertex-guard cut solved in the earlier Experiment v1. Do not equate these objectives or claim a vulnerability. |
| 5 | `OAI.WeakHessian.every_geodesic`; `OAI/Geometry/WeakHessian/Main.lean`; blob `a7f5316e9e9494e2ca155cfae3a763b88543a021` | Conceptual route from weak Hessian hypotheses to geodesic second-derivative bounds | Hypotheses include RCD space assumptions, support, Lipschitzness, weak Hessian upper bound. Does not certify molecular SCF curvature, orbital stability, or the earlier quadratic energy-defect model. Heavy dependency graph. |
| 6 | `OAI.BoundedTreewidthL1.main_theorem`; same TreewidthL1 source | Metric-embedding bounds for graph-based representations | Only consider after leaf-lemma portability and exact statement fidelity are proven; likely large transitive dependency closure. |

Comparator challenge configs include `CycleDecomposition.json`, `CompleteCrouzeix.json`, and `UniformSparsestCut.json`; they list the respective main theorem declarations and allowed axioms `propext`, `Quot.sound`, `Classical.choice`. A comparator config is a **verification target**, not evidence that this session recompiled or audited that result.

## Smallest useful next experiment

1. Acquire the immutable full upstream OpenAI `math` commit SHA and capture the observed Lean toolchain, Mathlib rev, selected source/module dependency graph, exact theorem type, and license in a manifest.
2. In an isolated scratch workspace, reproduce the selected `l1Append_norm_sub` declaration under the **upstream pinned environment** with independent checker and axiom audit. Do not compile all hundreds of papers.
3. Rephrase this compositional metric identity as a CACE experiment: represent two independent feature channels and compare the norm of the combined displacement with the sum of separate displacements; test exact rational finite-dimensional special cases and perturbations. A passed numerical test is **not** a proof.
4. Attempt a portable Lean version under **Expert Robot's existing 4.34.0 pin** without introducing upstream OAI as a runtime dependency. If compatibility fails, preserve the failure and do not update the production lock automatically.
5. Build a fresh CACE-specific theorem only after the bridge definitions are precise; make dependency, axiom, hidden-witness, direct replay, and register checks mandatory. No promotions or production policy changes.

## Security research continuation

The live PR #47 source-to-sink experiment already provides intentionally small offline AST fixtures. Separate concerns:
- Report graph extraction *completeness* and interpreter/normalizer semantics from proof that a cut intersects every modeled path.
- A finite guard-cut proof says nothing about paths omitted by a parser, external side effects, or unreachable/unsafe branch states.
- Before generalizing beyond bounded acyclic fixtures, falsify on cyclic CFGs and early exits, explicit aliasing, guard after sink, mutation after guard, and unsupported syntax. The deliberately narrow AST checker cannot certify general Python.
- Follow the repository's free-compute/Avrea half-month guardrails; do not run active internet target scans.

## Acceptance states

`found/source-inspected`: YES for the modules above.
`upstream-full-commit-pinned`: NO.
`reproduced-in-upstream-environment`: NO.
`cross-compiled-under-expert-robot-pin`: NO.
`registered-and-qualified-as-project-theorem`: NO.
`CACE-application-bridge-qualified`: NO.
`security-or-molecular-certification`: NO.

This document is a decision record and should not be treated as a green qualification artifact.
