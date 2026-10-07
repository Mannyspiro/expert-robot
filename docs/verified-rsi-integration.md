# Verified RSI integration — CACE + Expert Robot (October 2026)

## Current implementation

**Implemented:** `config/verified_rsi_integration_catalog.json`,
`scripts/plan_verified_rsi.py`, and
`tests/verified_rsi_planner_smoke.py`. The script ranks eight explicitly
registered improvement routes across CACE and Expert Robot. It provides a
Pareto frontier, preserves variety across proof, numerics, material design,
quantum and evidence acquisition, accepts optional grouped feedback, uses
the existing `estimate_generation_budget.py`, then caps proposed runs by
the explicitly supplied 2-vCPU-equivalent Avrea credit allowance. Default
available credit is **zero**; zero-spend CI creates a plan artifact without
executing any candidate.

The read-only adapter `scripts/collect_verified_rsi_signals.py` now accepts
reports from the pinned CACE FEM bridge, structural modeler, quantum RHF
worker cluster, or browser vision. It normalizes baseline observables and
source hashes; **no matched parent/child baseline or measured capability
gain is inferred**. Use:

```sh
python3 scripts/collect_verified_rsi_signals.py \
  --kind cace_bridge --input cace-nd-bridge.json \
  -o cace-rsi-baseline-signals.json
```

The catalog now records exact target repositories. An edit to
`morganaspim/Cace-app` is **not** eligible for
`Mannyspiro/expert-robot` automatic promotion; a separate CACE verifier,
lineage and authorization process is mandatory.

**Not implemented by this planner:** candidate code mutation, automatic
experiment execution, remote CACE deployment, verified performance gains,
model-weight updates, proof-signing or promotion. Those actions belong only
to the existing trusted collared RSI qualification, Lean checks, hidden
holdout benchmarks and promotion workflow. **The planner never grants them
permission.** The route weights are *research priors*, not measured gains.

```bash
python3 tests/verified_rsi_planner_smoke.py

# Produce a plan with no authorized execution or cloud credit spend:
python3 scripts/plan_verified_rsi.py \
  --remaining-avrea-credits 0 \
  -o rsi-plan.json

# Hypothetical allocation only, not a billable run or an account-usage check:
python3 scripts/plan_verified_rsi.py \
  --remaining-avrea-credits 240 \
  -o rsi-hypothetical.json
```

The planner cannot establish the Avrea account-wide balance; even when
given a nonzero amount, it creates an advisory allocation. The real
per-half-month accounting workflow remains the enforceable runtime guard.

## Ranked integration surfaces

| Route | CACE/Expert Robot target | Independent proof/evaluation work | Promotion restriction |
| --- | --- | --- | --- |
| Adaptive refinement | CACE exact geometry and mesh-adaptive solver | Lean midpoint geometry, implementation equivalence, sealed mesh holdout and error certificates | Only proved/per-instance symmetry reductions; never skip certificate |
| Recursive lemma factory | Expert Robot Lean proof-search and tactic routing | Pinned Lean, theorem-name-stripped and hidden hard-v2 proof tests | Qualified capability-only files, no evaluator changes |
| Sparse operator | CACE matrix assembly, solver and residual | Multiple reference PDEs, interval/residual consistency and memory checks | Do not change numerical truth conditions |
| Modeler topology | Research Object 3D/2D structural design | Keep-out/solid correctness, FEA, unseen loads and material bounds | Manual qualification, not production-ready claims |
| Quantum scheduler | Multi-CACE PySCF task distribution | Serial energy replay, basis convergence, independent model comparisons | Not electronic stability or atom production authority |
| Browser vision | Research source discovery and screenshot/glyph search | Adversarial webpages, image-grounding benchmark, independent witness identity | Web content never gets instructions/tool authority |
| Molecular/crystal screening | Matter Graph and simulation | Cross-model stability, uncertainty, independently reproduced labs | Never infer synthesis/manufacturing certification |
| Agent strategy | Route and memory selection | Task completion, blinded regression, collar/core integrity | No growth in permissions |

These priority hypotheses are seeded from code that already exists on the
research branch, **not evidence that the improvements work yet**.

## Modern sources: permissive ideas, independently implemented code

| Reference | License situation as researched | Permitted borrowing |
| --- | --- | --- |
| [OpenEvolve](https://github.com/algorithmicsuperintelligence/openevolve) | Apache-2.0 LICENSE | Concepts: algorithm variation, independent evaluators, candidate archives |
| [DGM](https://github.com/jennyzzt/dgm) | Apache-2.0 LICENSE | Concepts: stepping-stone lineages, self-improving code conditioned on benchmarks |
| [GEPA](https://github.com/gepa-ai/gepa) | MIT LICENSE | Concepts: reflection from full failure traces, Pareto selection |
| [DSPy](https://github.com/stanfordnlp/dspy) | MIT LICENSE | Concepts: module-specific prompt optimization with separate validation |
| [SWE-agent](https://github.com/SWE-agent/SWE-agent) | MIT LICENSE | Concepts: tool-based code repair, replayable tests |
| [OpenHands](https://github.com/OpenHands/openhands) | MIT core; other components may carry different conditions | Concepts: isolated tool execution and controller separation only |
| [AlphaEvolve](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/) | Public research description; no open-source grant assumed | High-level evaluator-driven program search only |
| [Autoresearch](https://github.com/karpathy/autoresearch) | License-file history uncertain; avoid importing files | Fixed-budget experiments and immutable evaluation concept only |

**Code-licensing provenance:** No third-party source was copied into these
implementation files. Concepts, names, and URLs are recorded for audit.
Installing an upstream component later requires a pinned upstream commit,
license/NOTICE capture, model-weight/data terms, transitive-dependency audit,
and an authorized review. Source-code licensing does **not** grant model-weight
or training-data licenses.

## RSI workflow

```text
External measurement artifact / failed Lean trace / residual history
    ↓ immutable SHA256 evidence; copied lineage-group observations capped
Trusted catalog + human-approved scope + feedback diagnostics
    ↓ bounded Pareto/diversity planner (advisory only)
Isolated candidate generation on capability-only branch
    ↓ parent/child stepping-stone comparison; no authority changes
Trusted verifier + pinned Lean build + CACE residual/certificate
    ↓ independent numerical benchmark + hidden holdout
Collar, authority non-expansion, rollback and lineage gates
    ↓ existing promotion evaluator (not this planner)
Qualified capability pointer (never automatic to production)
    ↘ retain negative results and superseded parent strategies
```

### Why this specific integration is important

GEPA-like failure summaries are especially useful for **why** a Lean tactic,
CACE residual bound or browser source match failed; DGM-like lineages avoid
discarding diverse successful strategies; AlphaEvolve/OpenEvolve-like
comparisons are a good fit for CACE's deterministic PDE/geometry work;
and autoresearch-style fixed budgets help avoid burning Avrea's short
half-month allowances.

The system deliberately distinguishes a *hypothesis* from a *formal theorem*,
a *passed smoke test* from *verified generality*, and a *qualified numerical
optimization* from a *physical manufacturing claim*.

## Next engineering step

1. Build trusted adapters from CACE solver traces, browser provenance
   artifacts, Lean replay logs and modeler holdouts into typed, immutable,
   independently reviewed feedback records.
2. Wire an offline model to **propose** scoped source edits and reflective
   failure explanations; the generator sees none of the holdout questions
   or production/promotion credentials.
3. Run real paired parent/child CACE and Expert Robot benchmark campaigns,
   calculate genuine effect sizes and confidence intervals, estimate optimal
   iteration depth from those measurements, and append negative evidence.
4. Apply the **existing** collared qualification gates unchanged, and only
   then consider automated capability-pointer promotion.

Do not manually add scripts, tests, CI workflows, secrets or trust policies
to the list of automatically mutable capability code just to enable RSI.
