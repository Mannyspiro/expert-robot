# Merlin Technical Specification: Lacunarity and Ideonomy v0.1

## Scope

This specification converts the Mathematical Structure Atlas proposal into a testable first implementation. It deliberately separates estimator definitions, semantic interpretations, empirical claims, and formal theorems.

## 1. Finite gliding-box lacunarity

Let a finite observed domain carry a nonnegative mass field f. For a window W_s at scale s and each permitted origin u, define m_u(s) as the sum of f over the translated window. For the finite set U_s of valid origins, define:

\[
\bar m_s=\frac{1}{|U_s|}\sum_{u\in U_s}m_u(s),\qquad
q_s=\frac{1}{|U_s|}\sum_{u\in U_s}m_u(s)^2.
\]

When the mean is positive:

\[
\Lambda(s)=\frac{q_s}{\bar m_s^2}
=1+\frac{\operatorname{Var}(m_u(s))}{\bar m_s^2}\geq 1.
\]

When the mean is zero, return an explicit undefined status such as NoMassAtScale. Never silently return zero.

## 2. Measurement record

Every output must include:

- scale and window dimensions;
- window shape and orientation;
- boundary policy;
- mass definition and units;
- observed domain and valid-window count;
- grid origin and stride;
- input resolution and preprocessing;
- first and second moments, variance, and lacunarity;
- numeric precision and accumulation method;
- uncertainty and sensitivity settings;
- source data hash, code version, and run provenance.

A lacunarity scalar without these fields is not a reproducible measurement.

## 3. Boundary and window policies

Implement boundary modes explicitly:

- valid_only: windows fully inside the observed domain;
- periodic: wrap coordinates at domain boundaries;
- padded: extend with a declared padding value;
- masked: omit invalid cells and record the valid mass support.

Initial window families: 1D intervals, 2D axis-aligned squares, and 3D axis-aligned cubes. Later versions may add rectangles, cuboids, disks, balls, rotated windows, and geodesic neighborhoods.

These policies define different estimands and must not be silently mixed.

## 4. Reference and optimized estimators

First implement a direct reference algorithm. It validates inputs, enumerates all permitted windows, computes their masses, and evaluates the moments. This slow implementation is the correctness oracle.

Then add prefix sums in 1D, integral images in 2D, and summed-volume tables in 3D. Exhaustively compare optimized and reference outputs on small arrays and compare seeded randomized fixtures.

For integer occupancy, use exact integer accumulators when safe. For real-valued mass, document floating-point precision and accumulation. Detect NaN, infinity, negative mass, overflow, empty domains, and zero mean.

## 5. Comparison protocol

Raw lacunarity depends on density, domain shape, window scale, orientation, boundary policy, and resolution. Comparisons must match these conditions or explicitly model their differences.

Always report the full scale curve and density. A normalized lacunarity curve may be useful, but every normalization must be named and documented. Never silently substitute normalized values for raw values.

## 6. Typed ideonomy hypergraph

Represent Merlin's idea space as a typed property hypergraph:

\[
G=(V,E,\tau_V,\tau_E,\sigma,\pi),
\]

where V contains concepts, definitions, hypotheses, experiments, proofs, datasets, and results; E contains typed relations or hyperrelations; tau assigns node and edge types; sigma stores provenance; and pi stores epistemic status and uncertainty.

Initial relation vocabulary:

- defined_by
- generalizes / specializes
- depends_on
- maps_to
- measured_by
- predicted_by
- tested_by
- proved_by
- contradicts
- equivalent_under
- requires_assumption
- has_counterexample
- derived_from

Do not collapse these distinct relations into one generic similarity edge.

## 7. Ideonomy candidate generation

Generate candidate research questions from typed slots:

\[
c=(D,O,R,T,S,M,H,X),
\]

where D is domain, O is object, R is relation, T is transformation, S is scale, M is measurement or invariant, H is hypothesis, and X is an experiment or proof route.

Prune in this order:

1. Type compatibility.
2. Domain and unit validity.
3. Mathematical well-formedness and explicit assumptions.
4. Known-equivalence and literature checks.
5. Small finite counterexample search.
6. Existence of a falsifiable consequence or proof obligation.
7. Estimated data, compute, and verification cost.

Novelty, expected utility, tractability, evidence quality, and uncertainty remain separate fields. A ranking score prioritizes work; it does not measure truth.

## 8. Graph lacunarity proposal

For a finite graph G=(V,E), choose a graph radius r and a neighborhood mass m_v(r), such as the number of nodes in the radius-r ball centered at v. Define:

\[
\Lambda_G(r)=
\frac{|V|^{-1}\sum_{v\in V}m_v(r)^2}
{\left(|V|^{-1}\sum_{v\in V}m_v(r)\right)^2},
\]

provided the mean neighborhood mass is positive.

This measures variation in local neighborhood mass. It is affected by degree distribution, component sizes, graph boundaries, and graph construction. Compare against degree-preserving null graphs where appropriate. It does not, by itself, establish missing knowledge or semantic novelty.

## 9. Formal properties for Lean

For a finite nonempty collection of nonnegative masses with positive mean, formalize:

1. Lacunarity is at least one.
2. Lacunarity equals one exactly when all masses are equal.
3. Reordering masses preserves lacunarity.
4. Multiplying every mass by a positive constant preserves lacunarity.
5. All-zero masses yield an undefined ratio under the positive-mean contract.

These theorems concern the finite estimator. They do not prove that an empirical sample follows a power law, that an image segmentation is correct, or that a material has a particular physical response.

Suggested Lean module: formal/MathAI/Lacunarity.lean. Define the mean and second moment over Fin n or a finite multiset, and make the positive-mean condition explicit. Prove the lower bound using nonnegative variance or Cauchy-Schwarz. Compile against the repository's pinned Lean and Mathlib versions before claiming formal qualification.

## 10. Synthetic qualification fixtures

Include:

- empty/all-zero field;
- one occupied cell;
- constant uniform field;
- periodic grid;
- two equal clusters;
- one compact cluster;
- seeded Bernoulli occupancy;
- deterministic Cantor-like and Sierpinski-like fields;
- translated and rotated copies;
- exhaustive small arrays for optimized/reference equality.

Each fixture records seed, input hash, scale set, boundary policy, expected properties, and output hash. Performance benchmarks are separate from correctness tests.

## 11. Engineering bridge

For CAD and material volumes, define the mass field explicitly: solid occupancy, void occupancy, material density, stress, temperature, or fluid velocity. Compute scale and orientation profiles. Compare matched designs and correlate descriptors with independently measured or simulated permeability, stiffness, energy absorption, stress localization, or thermal transport.

Correlation is not causation. Evaluate predictive claims on held-out geometries and report uncertainty. Lacunarity never replaces exact CAD constraints, collision checks, material laws, electrical rules, or engineering qualification.

## 12. Evidence receipt

Every result stores claim_id, claim_text, claim_kind, assumptions, method, source_commit, toolchain, input_hashes, output_hashes, seed, run_status, review_status, limitations, and counterexamples_checked.

Use distinct statuses: proposed, implemented, tested, formally_proved, independently_reviewed, empirically_supported, refuted, inconclusive.

A passing software test is not a formal proof. A formal proof of an estimator identity is not empirical evidence of a physical effect.

## 13. Completion gate

Do not call this increment complete until the direct estimator exists, optimized implementations match it, zero-mass and boundary behavior are explicit, synthetic fixtures are reproducible, Lean theorems compile on pinned dependencies, Avrea workflows pass on the exact candidate SHA, and CACE independently reviews assumptions and evidence classification.

Capability grows; authority never expands.