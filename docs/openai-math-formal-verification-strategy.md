# Universal mathematics verification queue: 2026-10-09

**Target:** pinned `openai/math@fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`.
**Catalogue:** `docs/openai-math-catalog-2026-10-09.json` lists 200 distinct main-result Lean declarations and exact comparator configuration paths. `docs/openai-math-all-manuscripts-index-2026-10-09.json` accounts for 719 manuscripts (718 CONTENTS links + one separate formalization-index PDF), with 546 without a corresponding formalization-index entry. This is source coverage, not proof validation.

## Verification stages, never conflated

- V0: metadata enumerated, SHA provenance linked, title/source recorded. **719/719** at the pinned version.
- V1: corresponding source/Comparator file exists, exact theorem identifier appears, axiom allowlist configuration inspected. **200/200 static declarations**, all 381 initial unique files retrieved; 24 comparator vs source module differences, 17 direct import paths, 7 pending transitive or checker validation.
- V2: original toolchain + mathlib/dependency lock reproducibly installed, source files built by upstream Lean kernel (full import closure), with time/memory/exit-code evidence. **Not yet independently established for 200**.
- V3: comparator challenge runs, declaration replay and `#print axioms`/Lean checker; no `sorry`/unapproved axioms; sealed challenge statement and exact theorem name. **Not yet independently established for 200**.
- V4: fidelity of mathematical definitions/quantifiers/hypotheses to manuscript claim, and independent counterexample/alternative checker for difficult claims. **Not done universally**. A kernel-valid formal theorem can still formalize the wrong statement or add assumptions.
- V5: CACE-specific type bridge, model assumptions, benchmarks and independent holdouts, protection gates. **Not done universally**.

## Cheapest reliable order of operations

1. `python3 scripts/check_openai_math_catalog.py ...`, `python3 scripts/check_openai_math_corpus.py ...`, `python3 scripts/screen_openai_lean_sources.py ...`. These are V0/V1 only.
2. `python3 scripts/plan_openai_math_formal_verification.py --batch-size 4 -o ...`. This generates 50 deterministic small batches containing all 200 main results, no duplication. It does **not** check Lean.
3. For V2/V3, isolate a selected batch in the upstream's official `leanprover/lean4:v4.34.1` environment and pinned Mathlib `d13f23b723b8a846827a245b89c10fc7d3f11612`; preserve transitive dependencies. Cache dependencies only by exact manifest hash and upstream commit, with no unpinned updates.
4. Run `lake env comparator ComparatorChallenges/<file>.json` only when `comparator`, `landrun`, `lean4export` are independently pinned/available (upstream comparator README explicitly lists these requirements). Plain `lake build` is useful V2 evidence but does **not** equal a successful comparator/independent verifier.
5. Output one receipt per target: immutable source commit, exact theorem signature, comparator challenge, dependency lock SHA, compilation result, axiom audit, stdout/stderr digest, runtime, worker type, failure reason, mathematical-statement correspondence status. Never promote a missing receipt.
6. Start with one cost-bounded V2 experiment. Expand only if useful cache reuse and runtimes make another bounded batch cost-effective. Free CI before Avrea; use the Phoenix 1500 weighted-credit half-month preflight and one-job rule before any Avrea allocation.

## Biology mathematics bridge

`formal/MathAI/Bio/ReactionConservation.lean` contains three **candidate** exact rational statements for `E+S <-> ES -> E+P` stoichiometry: `total_enzyme_conserved`, `substrate_moiety_conserved`, and `reversible_flux_merged`. The project Lean workflow must pass before marking candidates qualified.

`scripts/experiment_biochemistry_stoichiometry.py` contains 24 exact-rational discrete steps over three synthetic holdouts, a mutation and a reversible column-compression equivalence. A passing toy benchmark is not biological calibration, physical truth, a verified CACE runtime or an actual speedup.

## Bounded recurring improvement principle

Formal proofs justify possible implementation rewrites, not their authority. For each proposed optimization: attempt a counterexample; validate mathematical applicability; independent executable oracle; record measured runtime benefit or harm; preserve locked rollback and host authority. No self-modification of policy/verifier/collar, and no unattended promotion.
