---
name: cace-biochemistry-proof-loop
description: Evidence-audited study of biology and biochemistry with exact chemistry, simulation, counterexample search, Lean statements, and tightly qualified improvements.
---

# CACE Biochemistry Proof Loop

Use this skill whenever a project task asks Expert Robot/CACE to learn biology or biochemistry, evaluate a molecular claim, propose a new model, or optimize a biophysical computation.

1. Begin with the biological question and identify the level: molecular graph, quantum/force field, static structure, conformational ensemble, enzyme mechanism, reaction network, cell, tissue, or organism. Never silently move claims across levels.
2. Retrieve primary research and reproducible datasets. Record source URL, version, retrieval date, organism, assay conditions, uncertainty, contradictory observations and applicable license. Distinguish textbook background, peer-reviewed experiments, AI predictions, model hypotheses and Lean theorems.
3. Capture species, amounts, units, compartments, atom/charge balance and stoichiometric matrix before an ODE/PDE; reject missing reactions and dimensionally inconsistent rates. If SBML is imported, fail closed on unsupported packages or implicit units.
4. Make a minimal baseline executable in a controlled environment; define negative controls, perturbations, boundary/degenerate cases, blind holdouts, and an independent arithmetic or numerical oracle. Never call toy simulations physical validation.
5. Mine candidate laws from output; for any conservation law, verify its left-nullspace condition, try broken stoichiometric columns, construct an exact rational witness, and formulate an independently checkable Lean theorem.
6. Seek computational improvements (sparse vectorization, reaction-flux merging, symmetry, adaptive timestepping), but first establish semantic equivalence under explicit preconditions and test against a separate implementation. Report exact operation counts separately from measured speedups.
7. Promote **no** result unless source SHA, Lean-independent checking, axiom audit, experimental holdouts, CACE interface validation, no-regression, rollback, and same-or-less authority gates are all satisfied. An optimization that passes mathematics alone is still unqualified.
8. Maintain a dated feedback ledger of hypotheses, evidence, failed experiments, revisions, and expected information gained per compute-minute. Prefer next work with highest falsifiability and useful transfer.
9. If a prior attempt fails, change only the test/model/proof candidate needed to address that failure; rerun skeptics and hidden cases. No autonomous production deployment, external service scanning, wet-lab organism manipulation, new permissions, or self-authorization.
10. Where cost is significant, estimate useful batch size and expected failure modes first. Use free local or GitHub-hosted compute, then Avrea only after the 1500-weighted-credit half-month account/preflight admits the reservation. Preserve CI artifacts and finite execution limits.

## Output contract
Produce: verified facts; model assumptions; source provenance; executable evidence; independent checker outcome; counterexamples; theorem statement; CACE applicability assumptions; observed speed/resource change; blockers; ranked next experiment. Explicitly say `not verified` when any required stage has not passed.

## Domain guide
Read `docs/biochemistry-research-program.md` for foundational topics, curated standards and source registry. Prefer harmless toy enzyme networks until field units, benchmark reproducibility and solver contracts have been demonstrated.
