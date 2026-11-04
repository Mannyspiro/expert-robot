# Merlin Fractal Engineering Research v0.1

## Purpose

Add a multiscale measurement and inference layer to Merlin's Continuum Mathematics / FIND-N architecture. Fractal analysis is treated as one family of descriptors for scale-dependent engineering structure, not as a universal quality score.

The guiding pipeline is:

**geometry across scales → relational structure → physical mechanism → measured property → engineering function**

A design is fractal-inspired when it deliberately repeats or varies a motif across a finite hierarchy. A manufactured design has finite iteration depth and a smallest feature size; it must not be described as an infinite mathematical fractal without a precise idealized model.

## 1. Mathematical foundations

### 1.1 Similarity dimension

For an ideal self-similar construction with N copies per iteration and linear scale ratio r, where 0 < r < 1, the similarity dimension candidate is

\[
D_s = \frac{\log N}{\log(1/r)}.
\]

Equality between similarity dimension and Hausdorff dimension requires additional mathematical conditions on the construction; it must not be inferred from the formula alone.

### 1.2 Box-counting dimension

For a set S, let N(epsilon) be the number of boxes of side epsilon required to cover S. When the limit exists,

\[
D_B = \lim_{\epsilon\to 0}
\frac{\log N(\epsilon)}{\log(1/\epsilon)}.
\]

For a finite manufactured object, estimate a slope only over a declared, observed scaling interval. Report the interval, fit residuals, sampling resolution, segmentation method, uncertainty, and sensitivity to box orientation and grid placement. Do not extrapolate below the manufacturing or measurement cutoff.

### 1.3 Descriptors beyond one dimension

Record at least:
- estimated box-counting dimension and fitting interval;
- hierarchy depth and scale ratio;
- lacunarity / spatial heterogeneity;
- anisotropy and orientation distribution;
- connectivity and topology;
- pore / feature-size distribution;
- surface roughness or interface complexity;
- uncertainty and measurement resolution.

Structures with similar estimated dimensions can have different void distributions, connectivity, stress concentrations, and mechanical behavior. Fractal dimension alone is therefore insufficient.

### 1.4 Multifractal extensions

Where a single exponent fails to describe heterogeneous scaling, investigate generalized dimensions D(q) and a multifractal spectrum. Treat this as a separate model family requiring adequate data and sensitivity analysis, not as an automatic upgrade.

## 2. Continuum-composite and FIND-N integration

Represent an engineering candidate as a multiscale continuum-composite object:

\[
\mathcal E =
(\mathcal G,\mathcal H,\mathcal R,\mathcal M,\mathcal B,\mathcal Y,\mathcal U)
\]

where:
- G: geometry at each scale;
- H: hierarchy / adjacency / hypergraph relationships;
- R: coordinate frames and scale transformations;
- M: material and constitutive models;
- B: boundary and loading conditions;
- Y: measured responses and engineering functions;
- U: uncertainty, provenance, and applicability conditions.

The representation graph connects CAD geometry, meshes, graphs, tensors, images, simulation fields, and learned embeddings. Every mapping records whether it is invertible, approximate, lossy, or merely correlational.

FIND-N roles:
- Induction: infer candidate scaling laws and recurring motifs from measurements.
- Abduction: propose mechanisms explaining observed cross-scale behavior.
- Deduction: derive consequences from declared geometry, constitutive laws, and boundary conditions.
- Fuzzy logic: express graded membership / compatibility when categories are genuinely vague.
- Probability and measurement uncertainty: remain separate from fuzzy membership.
- Paraconsistent handling: retain conflicting measurements or models without treating contradiction as proof.
- Verification: counterexamples, sensitivity analysis, reproducible simulation, and Lean proofs of conditional mathematical claims.

## 3. Engineering applications to investigate

### 3.1 Mechanical metamaterials and lattices
Compare bending-, stretching-, membrane-, and buckling-dominated mechanisms across hierarchy levels. Measure stiffness, strength, energy absorption, deformation localization, fatigue response, and failure evolution.

### 3.2 Porous and cementitious materials
Measure pore-size distributions, connectivity, permeability, moisture transport, thermal transport, compressive behavior, and fracture. Separate image-derived descriptors from experimentally measured properties.

### 3.3 Fracture and surface morphology
Track crack-path tortuosity, roughness, branching, energy dissipation, and scale-dependent damage. A correlation between roughness dimension and energy dissipation is material- and test-dependent.

### 3.4 Thermal and fluid systems
Investigate hierarchical channels, heat exchangers, porous flow paths, and coupled transport. Include pressure drop, heat transfer, clogging, manufacturability, and fouling.

### 3.5 CAD assemblies and wiring / harness systems
Use multiscale geometry for component features, subassemblies, cable bundles, routing corridors, and enclosure layouts. Fractal descriptors may characterize geometry or routing complexity, but must not replace exact clearance, bend-radius, collision, electrical, thermal, or standards checks.

## 4. Measurement and inference protocol

For each candidate architecture:

1. Define the engineering function and hard constraints before optimizing.
2. Acquire geometry and measurements with traceable calibration and resolution.
3. Generate scale-space representations using declared segmentation and sampling settings.
4. Estimate scaling descriptors over a justified finite range.
5. Fit candidate scaling laws and compare against non-fractal, periodic, random, and conventional hierarchical baselines.
6. Measure physical response under controlled loading and boundary conditions.
7. Use sensitivity analysis to separate geometry effects from material, process, and boundary-condition effects.
8. Validate predictions on held-out geometries, specimens, or operating conditions.
9. Record counterexamples and model failure regions.
10. Promote only the specific model claims supported by reproducible evidence and independent review.

Do not optimize fractal dimension by itself. Use multi-objective engineering evaluation, such as mass-specific stiffness, energy absorption, permeability, thermal performance, fatigue life, manufacturing cost, tolerance sensitivity, inspectability, and repairability, subject to non-negotiable constraints.

## 5. First benchmark: finite hierarchical lattice

Create matched candidate families:
- conventional periodic lattice;
- single-scale lattice;
- finite self-similar hierarchy;
- randomized hierarchy;
- topology-matched non-fractal control.

Hold material, mass or relative density, external envelope, boundary conditions, and loading protocol constant where possible. Sweep hierarchy depth and scale ratio. Compare:
- stiffness / mass;
- peak load / mass;
- absorbed energy / mass;
- deformation localization;
- failure initiation and propagation;
- fatigue response;
- manufacturing resolution and defect sensitivity.

The objective is to determine when hierarchical scaling contributes useful performance, not to assume that more iterations or larger fractal dimension are better.

## 6. Lean formalization plan

The initial Lean increment proves only finite hierarchy identities:
- recursive cell counts compose multiplicatively;
- recursive scale ratios compose multiplicatively;
- a one-step weighted self-similarity balance propagates to every finite depth;
- a scale ratio in [0,1] stays bounded under finite iteration;
- nominal scale is nonincreasing with hierarchy depth.

File: `formal/MathAI/FractalEngineering.lean`.

These are foundational conditional theorems, not proofs of a measured fractal dimension, a physical constitutive law, structural integrity, safety, or engineering optimality.

Next formalization targets:
1. Similarity-dimension algebra under explicit assumptions.
2. Box-counting slope identities for an exact power-law model.
3. Hausdorff-dimension invariance under bi-Lipschitz equivalence, using Mathlib's existing metric-space results.
4. Scale transformation composition and invariants.
5. Error bounds for finite-scale estimates under explicit model assumptions.

Mathlib documents Hausdorff measure and Hausdorff dimension in:
https://leanprover-community.github.io/mathlib4_docs/Mathlib/MeasureTheory/Measure/Hausdorff.html
https://leanprover-community.github.io/mathlib4_docs/Mathlib/Topology/MetricSpace/HausdorffDimension.html

## 7. Avrea / PR qualification contract

The PR should trigger the repository's existing Avrea CI and dedicated Lean qualification workflow. A passing workflow must be bound to the exact PR head SHA and should retain:
- run URL and run ID;
- exact commit SHA;
- Lean toolchain and Mathlib dependency revision;
- theorem source hashes;
- successful build / theorem compilation;
- theorem-specific axiom report and allowlist result;
- test and experiment artifact hashes;
- resource usage and failure logs.

Do not claim Avrea passed until the actual run completes and its exact SHA matches the PR head. A Lean proof receipt proves the formal proposition under its assumptions; it does not authenticate measurements or validate a physical engineering model.

## 8. Evidence and interpretation boundaries

- A fitted power law over a finite interval is evidence of approximate scaling over that interval, not proof of infinite self-similarity.
- A fractal descriptor is a geometric statistic, not a direct measure of strength, safety, intelligence, or quality.
- Simulation convergence is not experimental validation.
- A correlation between dimension and performance does not establish causation.
- Fractal-inspired structures may be more accurately described as finite hierarchical architectures.
- Engineering release requires domain-specific measurements, applicable standards, and independent human review.

## 9. Research sources

- Frischer et al. (2025), *Fractal Theory: A Comprehensive Review of Applications Across Engineering Disciplines*, DOI: https://doi.org/10.1142/S0218348X25300089
- Zhao and Wang (2026), *A Review on Fractal Technology Applications in Cementitious Materials: Theory and Limitations*, Fractal and Fractional 10(3), 180, DOI: https://doi.org/10.3390/fractalfract10030180
- *Hierarchical and Fractal-Inspired Mechanical Metamaterials: A Mechanics-Oriented Review of Multiscale Design, Strength, Deformation, and Energy Absorption*, Materials (2026), DOI: https://doi.org/10.3390/ma19163432
- Lean Mathlib Hausdorff measure and dimension documentation (links above).

## 10. Merlin implementation sequence

1. Add typed scale-space and hierarchy descriptors to Engineering IR.
2. Add deterministic box-counting / lacunarity measurement with explicit finite scale windows.
3. Add geometry-to-mesh-to-image provenance and round-trip hashes.
4. Add finite hierarchical lattice generators and matched baselines.
5. Add simulation adapters and held-out benchmark manifests.
6. Add evidence receipts and CACE independent qualification.
7. Add Lean formalization for the exact mathematical claims.
8. Integrate outputs with CAD visualization and XMG-S operators.

Capability grows, authority never expands.
