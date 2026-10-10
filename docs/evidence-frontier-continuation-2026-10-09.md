# Evidence-frontier continuation — 2026-10-09

This branch adds **candidate verification tools**, not completed formal or
experimental qualifications. It is based on parent head
`06a3dc89a5c457bb974d90be1d5bee982e1cb059` and is intended for review
against `research/magick-ir-v0-1` (draft PR #47).

## Ranked implementation and next execution

1. **Upstream mathematical proof replay.** The selected target retains immutable
   upstream, Lean 4.34.1 and Mathlib revision pins. The sequential CI job now
   adds a per-target JSON receipt recording the exact declaration, source/module
   digest, manifest digest, declared axioms, CI run and source revision.
   `audit_openai_lean_receipt.py` refuses missing/duplicated `#print axioms`
   output, unauthorized axioms, mismatched source pins or a non-success
   Lean checker step. It is only meaningful **after** the workflow genuinely
   completes; synthetic smoke fixtures do not validate any OpenAI theorem.
   Comparator challenge V3 and manuscript statement fidelity V4 are still open.

2. **Pinned carbon-metabolism intake triage.** `BIOMD0000000051` remains
   quarantined for upstream unit/consistency problems (40 observations, three
   `10541` kinetic dimensional errors in the previous pinned run). The
   separate `triage_biomodels_consistency.py` generates a line/column and
   source-digest-linked diagnostic report even when the intake step exits
   nonzero. It never rewrites the public model or downgrades validation errors.
   Corrected models need a separately pinned artifact and independent numerical
   comparison before being considered physically or biologically credible.

3. **General exact reaction conservation.** The rational RREF implementation
   determines a basis for the left nullspace of arbitrary small stoichiometric
   matrices, then verifies the identity
   `wᵀ(x + Δt (S v + b)) - wᵀ x = Δt wᵀ b`
   for several held-out toy networks. It deliberately detects a lost reactant,
   explicit open-boundary contributions and mixed amount/concentration units.
   `formal/MathAI/Bio/NetworkConservation.lean` generalizes the single-column
   algebraic step to arbitrary finite species and is linked into the audited
   root. The exact-head Formal Qualification workflow must succeed before this
   counts as kernel-checked.

4. **CACE independent benchmark screen.** A candidate must provide sealed
   holdouts, matching SHA256 fixture identifiers, independent residual checks,
   finite nonnegative timings, no residual regression and an aggregate speed
   improvement. The screen rejects missing lineage, regressions and unequal
   inputs. This is *not* an attestation of honest timers, a live CACE benchmark
   or permission to promote an optimization. Run actual CACE backend trials
   and compare holdouts before any gain claim.

5. **Unchanged RSI authority.** Every new receipt explicitly records
   `promotion_authorized=false`. Existing collar, scope, rollback, verifier,
   independent benchmark, expense and authority-nonexpansion gates remain
   authoritative. A successful unit test or synthetic improvement cannot
   bypass them.

## Cheap local reproduction

```sh
python3 tests/research_validation_frontier_smoke.py
python3 scripts/experiment_general_reaction_conservation.py -o /tmp/general-conservation.json
```

Use the `Evidence Frontier Validation` workflow for the same checks in
GitHub. The formal replay uses the existing serial research validation lane;
no new Avrea or other paid resources are allocated by this patch.

## Cross-chat evidence discipline

After CI runs, record exact commit, workflow run ID, selected theorem, axiom
receipt, scientific-model diagnostic artifact and individual test conclusions.
Do not reinterpret **queued**, **failed**, **skipped** or **fixture-only**
verification as an independent proof or measured performance improvement.
