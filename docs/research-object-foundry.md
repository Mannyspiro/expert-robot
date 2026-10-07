# CACE Research Object Foundry

## Goal

Give CACE the ability to generate **physical objects as scientific hypotheses**.

The design philosophy is inspired by NASA's public Evolved Structures workflow:
define preserve geometry, obstacle/keep-out geometry, loads and requirements;
generate candidate shapes; validate them with physics/FEA; then check
manufacturability. We use the published workflow concepts, not NASA proprietary
or restricted implementation code.

CACE extends that idea beyond mechanical structures:

```
research question
  -> exact/parametric design space
  -> preserve geometry
  -> keep-out geometry
  -> materials
  -> fields / loads / boundary conditions
  -> multi-objective generation
  -> exact geometry validation
  -> mesh
  -> multiphysics solve
  -> residual + a-posteriori error
  -> interval/certified bound
  -> manufacturability / fabrication simulation
  -> novelty-quality archive
  -> Expert Robot chooses next candidates
  -> repeat
```

## Why this belongs in CACE

CACE already has the right downstream structure:

```
geometry
-> coordinate/shape functions
-> sparse operator
-> solver
-> residual
-> error estimator
-> certified bound
-> adaptive refinement
-> certificate
```

The Research Object Foundry adds the missing upstream generator.

## Object representations

The typed interface allows:

- exact CSG;
- parametric geometry;
- implicit signed-distance fields;
- voxels / material-density fields;
- surface meshes;
- volume meshes;
- hybrids.

Exact CSG and parametric objects should be preferred when they can express the
design because they preserve reproducibility and formal reasoning.

## Generation methods

Candidate generation may use:

- deterministic parameter sweeps;
- gradient shape optimization;
- topology optimization;
- evolutionary search;
- quality-diversity search;
- surrogate models;
- symbolic geometry rewrites.

No generator certifies its own output.

Every candidate goes through independent geometry, physics, and evidence gates.

## Connection to historical-circle research

Historical diagrams become one possible **seed family** rather than privileged
truth.

For example:

```
historical circle topology
-> exact geometry seed
-> bounded geometric mutations
-> acoustic/material/orientation variants
-> CACE simulation
-> experimental prediction
-> physical bench test
```

Expert Robot can then ask whether historically conserved geometry occupies a
physically unusual part of design space or behaves no differently from matched
controls.

That lets us investigate geometry/material/acoustic interactions without
presuming that the historical supernatural interpretation is correct.

## Commercial-license requirement

The core Foundry must remain suitable for unrestricted commercial products.

Default dependency policy:

- PREFERRED: Apache-2.0, MIT, BSD-2-Clause, BSD-3-Clause, ISC, similarly permissive licenses.
- CASE-BY-CASE: MPL-2.0 or weak-copyleft libraries behind a clean boundary.
- EXCLUDED FROM CORE BY DEFAULT: GPL, AGPL, SSPL, research-only, non-commercial, field-of-use restrictions, government-purpose releases, custom commercial licenses, or source that requires a separate NASA/software license.
- NOSA-licensed NASA code is reference/inspiration only unless separately reviewed and approved.
- Patents are evaluated independently from copyright/software license.

Recommended implementation stack candidates:

- our own CACE exact-geometry layer;
- CadQuery scripting where useful (Apache-2.0), subject to dependency audit;
- Manifold for robust manifold mesh booleans (Apache-2.0);
- Open3D for mesh/point-cloud processing (MIT);
- MFEM for FEM kernels (BSD-3-Clause), where it fits CACE's verified numerical contracts.

NASA Cart3D and CBAERO are **not** core dependencies: current NASA catalog
materials show release/licensing restrictions. Their architecture can inspire
interfaces, meshing and analysis workflows without importing their code.

OpenVSP is NOSA 1.3, not one of our preferred permissive licenses, so it is
treated as an external reference/interchange target rather than a core
dependency unless legal review explicitly approves it.

## Patent policy

"Open source" does not automatically mean "patent-risk free."

CACE therefore separates:

1. copyright/software license compatibility;
2. patent rights and patent exhaustion/grants;
3. implementation provenance.

We implement public engineering concepts independently and retain design notes
showing provenance. If a feature is known to correspond closely to an active
patent claim, it stays disabled until reviewed or is implemented by a clearly
non-infringing alternative.

## Candidate acceptance

A generated object may advance only if it passes:

1. exact geometry / topology validity;
2. material-property provenance;
3. numerical convergence;
4. residual and uncertainty checks;
5. requested interval/certified bounds;
6. safety constraints;
7. manufacturing constraints;
8. holdout / cross-model checks where appropriate;
9. provenance and dependency-license audit.

A visually interesting mesh is not a research result.
