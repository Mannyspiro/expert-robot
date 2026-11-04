# Merlin Research Prompt — Real-World Equation Atlas and Math Kung Fu

Use Merlin's full relevant project context to research, rank, derive, compare, and teach mathematical models with high practical value in the real world.

## Mission
Build a 100-entry Real-World Equation Atlas across engineering, physics, robotics, computation, biology, finance/operations, signals, networks, and scientific inference. The objective is not to declare one universally optimal equation. For each application, determine which model is most appropriate under explicit requirements, assumptions, constraints, uncertainty, data availability, and computational budget.

## Required workflow
1. Enumerate application domains and candidate mathematical structures using Ideonomy.
2. Search authoritative literature and standards; preserve source metadata and publication dates.
3. Normalize each model into typed variables, units, domains, assumptions, boundary/initial conditions, and valid operating regime.
4. Derive the equation from first principles where feasible; distinguish derivation from empirical fit.
5. Compare alternatives on common data and common constraints. Evaluate predictive error, computational cost, complexity, uncertainty, sensitivity, robustness, interpretability, and constraint satisfaction.
6. Test dimensional consistency, limiting cases, conservation/invariance properties, numerical stability, convergence, and reproducibility.
7. Use simulation/CAD only when it adds evidence. Record code, solver, mesh/time step, parameters, seeds, tolerances, and residuals.
8. Seek independent verification. Use Lean for formalizable claims; never present numerical evidence as proof.
9. Assign evidence status: ESTABLISHED, REPRODUCED, FORMALLY_VERIFIED, COMPUTATIONAL_CONJECTURE, UNVERIFIED, or REFUTED.
10. Convert verified material into Math Kung Fu lessons: visual intuition, shape/operator recognition, equivalent representations, short derivation, real-world application, recall exercise, and advanced extension.

## Merlin integration
- Ideonomy enumerates the model space.
- XMG represents one object across multiple typed coordinate frames and transformations.
- Equation Atlas stores canonical equations and metadata.
- Academic Spider gathers literature and provenance.
- Simulation/CAD explores physical behavior.
- Independent verification and Lean audit claims.
- CACE/Expert Robot review evidence, reproducibility, and promotion.
- Preserve the principle: capability grows, authority never expands.

## XMG requirements
Represent an object as X = (O, {F_i}, {T_ij}, Ops, Inv), where O is the underlying object, F_i are typed frames, T_ij are mappings, Ops are operators, and Inv are invariants. Distinguish coordinate changes from physical transformations, projections, embeddings, and lossy representations. Track information loss and transformation provenance. Support 2D/3D/4D/5D+ representations without pretending that extra coordinates automatically correspond to physical dimensions.

## Model-selection objective
Use a transparent application-specific objective such as
J(M) = w_p E_prediction + w_c E_compute + w_k E_complexity + w_u E_uncertainty + w_s E_sensitivity + w_r E_robustness + penalties_for_constraint_violation.
Weights and hard constraints must be justified by the application. Safety-critical constraints may be non-negotiable. Report Pareto trade-offs rather than hiding them in one score.

## Required entry schema
For each atlas entry record:
- ID, domain, application, model family, canonical equation(s)
- variables, units, domains, assumptions, conditions
- what the equation says intuitively and geometrically
- where it is useful and where it fails
- alternatives and why one might be preferred
- numerical/experimental validation protocol
- uncertainty and sensitivity requirements
- formalizable claims and proof obligations
- source citations with claim-to-source mapping
- evidence status and confidence rationale
- Math Kung Fu lesson mapping and cross-domain analogies

## Quality gates
No invented citations, data, benchmarks, proof results, or Merlin execution claims. Label assumptions and unknowns. Do not promote an equation merely because it is elegant or novel. Require independent reproduction for important claims. Keep speculation separate from established mathematics and engineering practice.

## Output
Produce the 100-entry atlas, a source register, a model-selection guide, a verification plan, a Math Kung Fu lesson sequence, and a machine-readable schema. Save every output in the Merlin repository under docs/research/real-world-equation-atlas/. Use a feature branch and a reviewable pull request; do not modify protected main directly.
