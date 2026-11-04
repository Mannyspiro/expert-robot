# Merlin Equation Atlas — Phase 0.3 execution plan

## Objective
Move from a working starter atlas to an evidence-bearing research system that can safely feed Merlin, XMG, CAD/engineering workflows, and Math Kung Fu. A result is promotable only when its evidence is reproducible and its assumptions remain visible.

## Workstream A — Complete the 100-entry inventory
For each RWEA entry:
- Preserve a stable ID and versioned equation text.
- Record every variable, tensor/index role, unit, SI base-dimension vector, and admissible domain.
- Record coefficient dimensions; never infer a coefficient as dimensionless merely because it is written as a scalar.
- State assumptions, initial conditions, boundary conditions, validity regime, and known failure modes.
- Link each equation term and nontrivial assumption to a source passage, DOI, standard, or textbook section.
- Distinguish a source supporting the equation's form from a source supporting a particular application or parameter value.

Deliverables: normalized entries 001–100, source coverage report, schema validation, and an unresolved-items register.

## Workstream B — Evidence receipt contract
Every research result should carry:
- stable claim/equation ID and version;
- source URLs/DOIs, retrieval date, exact cited section/page, and content hash where available;
- assumptions, units, dimensional derivation, and validity regime;
- code commit, dependency lock, runner image/toolchain, command, seed, tolerances;
- test names and pass/fail output;
- artifact URI and SHA-256;
- Lean theorem name, imported axioms, and compiler/toolchain version when formalized;
- reviewer/approval state and supersession links.

Receipts must be append-only. Corrections create a new receipt and preserve the old one. Never allow a model-generated summary to overwrite source evidence.

## Workstream C — Verification ladder
Use independent, explicitly named statuses:
1. UNVERIFIED — captured but not checked.
2. SOURCE_SUPPORTED — source supports the stated mathematical form and assumptions.
3. DIMENSIONALLY_CONSISTENT — all declared terms and sides pass dimensional checks.
4. SYMBOLICALLY_CHECKED — declared symbolic identities/derivatives pass.
5. COMPUTATIONALLY_REPRODUCED — pinned experiment passes and artifact is archived.
6. EMPIRICALLY_VALIDATED — independently sourced measurements or benchmark data support the model within a stated regime and uncertainty.
7. FORMALLY_VERIFIED — a Lean theorem compiles under the pinned project with explicit assumptions and audited axioms.
8. REFUTED / SUPERSEDED — contradicted in the declared regime or replaced by a newer version.

These are evidence dimensions, not a single linear quality score. For example, a theorem can be formally verified while its physical model remains empirically unvalidated. Preserve separate fields rather than collapsing all evidence into one label.

## Workstream D — Better numerical science
For each executable model, add:
- parameter sweeps and sensitivity analysis;
- solver/time-step/grid convergence checks;
- stability and conservation/invariant checks where applicable;
- residual and error norms with stated units;
- uncertainty propagation or Monte Carlo analysis when justified;
- comparison to independent benchmark datasets;
- negative tests for out-of-regime inputs.

Start with heat diffusion, logistic growth, least squares, Fourier sampling, and constrained optimization. Synthetic experiments must be labelled synthetic.

## Workstream E — Lean formalization
- Keep theorem candidates in a separate registry from verified theorems.
- Formalize pure mathematical claims, not unsupported physical interpretations.
- Include explicit hypotheses for positivity, smoothness, invertibility, boundedness, convexity, or boundary conditions.
- Run the separate formal-qualification workflow with pinned Lean/Mathlib versions.
- Capture `#print axioms` output and reject accidental use of `sorryAx`, unapproved axioms, or hidden assumptions.
- Link theorem names to the exact equation-entry version and source receipt.
- Do not promote a theorem merely because the Python CI passed.

## Workstream F — XMG and engineering geometry
Represent each model as a typed object with:
- source frame, target frame, coordinate convention, units, and basis;
- transform kind: passive coordinate change, active transformation, projection, embedding, measurement, or basis change;
- invariant quantities and expected information loss;
- transformation graph and reversible/irreversible edge labels;
- numeric tolerances and round-trip tests.

Generate 2D/3D/4D+ views only from the same typed model data used by tests. Begin with the existing garden geometry, heat field, and robot-pose examples. Export deterministic SVG first; add GLTF after schema and transform tests pass. For CAD/PCB use explicit physical units and connectivity constraints; visual appearance alone is not proof of manufacturability.

## Workstream G — Research-to-learning pipeline
A Math Kung Fu lesson may be generated from an entry only when:
- the mathematical statement and assumptions are stable;
- at least one worked example reproduces;
- units and dimensions are explained;
- limitations and one counterexample/out-of-regime case are included;
- the lesson can distinguish intuition from theorem.

Keep each lesson short, introduce at most one or two new concepts, include a recall prompt, and adapt the next exercise to observed errors. Do not teach a conjecture as an established fact.

## Recommended execution order
1. Source and schema coverage report for entries 001–020.
2. Fix schema mismatch between the normalized tranche and canonical entry schema; validate both with automated tests.
3. Complete normalized tranche 021–040, prioritizing core engineering, signal processing, dynamics, geometry, and inference.
4. Expand executable dimensional checks for 001–040.
5. Add convergence/sensitivity experiments to the five existing baselines.
6. Execute formal-qualification workflow and inspect Lean logs.
7. Build evidence receipt writer and immutable receipt tests.
8. Add XMG typed serialization and SVG export.
9. Continue 041–100 in domain-balanced batches.
10. Generate lessons from entries that pass the appropriate gates.

## Guardrails
- No fabricated citations, measured data, proof results, or runner outcomes.
- A source is evidence only for the claims it actually supports.
- A passing unit test is not an empirical validation.
- A dimensional pass is necessary but not sufficient.
- A Lean proof validates the theorem as stated, not the real-world model's assumptions.
- Keep worker permissions narrow, research actions read-only by default, and all merge/promotion actions approval-gated.
- Capability grows, authority never expands.
