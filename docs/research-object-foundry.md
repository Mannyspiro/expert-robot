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


## Implemented modeler v0.2 (October 2026)

The initial research object generator is now an executable deterministic
Python (stdlib-only) geometry front end:

```sh
python3 scripts/generate_research_object_candidates.py \
  config/examples/research_object_demo.json \
  -o research_candidates.json

python3 scripts/export_research_object_obj.py \
  config/examples/research_object_demo.json \
  -o candidate-preview.obj
```

### What it currently implements

- Preserved 3D mounting/interface points, bounded design space.
- Axis-aligned 3D keep-out boxes, including user clearance plus **half the
  assumed strut diameter** to protect the centerline's cylindrical envelope.
- Correct segment-vs-AABB intersection, including parallel-to-slab cases.
- Candidate complete graphs, nearest trees, perimeter loops, centroid stars,
  obstacle-aware routed trees and obstacle-aware routed loops.
- Shortest-path detours using geometric obstacle corners and a deterministic
  visibility network; geometric validity of every selected centerline checked.
- Connectivity, boundary-exclusion and obstacle-exclusion checks.
- Length, graph-edge redundancy (bridge count) and cylindrical volume/mass
  **proxies**; approximate Pareto frontier for material use vs redundancy.
- A triangulated capped-cylinder OBJ **preview**, with separate overlapping
  cylinders at junctions.

### Not yet implemented

The OBJ preview is **not watertight joined CAD**, and is not a manufacturable
solid. A centerline/approximate-cylinder check does not replace solid boolean
operations, junction stress analysis, geometric tolerances, collision checks
for actual fabrication, FEA, or a certified load-dependent error bound.

The next implementation milestones, in order, are:

1. Solidification with exact or audited manifold geometry; verify joint and
   design-boundary clearances on the solid, not only on centerlines.
2. Supports, load cases, material parameter provenance, realistic beam/
   elasticity solve, and meaningful stress/displacement/volume measurements.
3. CACE adaptive mesh and certified error/bound route, with fail-closed
   fallback when a continuum certificate is unavailable.
4. Multiobjective search beyond seed families, holdout testing, ablation, and
   novelty archive; only certified candidates advance into fabrication review.

### Validation

A separate lightweight GitHub-hosted workflow
`.github/workflows/research-object-modeler.yml` runs regression tests
and uploads both the JSON candidates and OBJ preview without consuming Avrea
runner credits. The tests cover the former false-positive box-intersection
bug and forced obstacle-avoiding detours, including rejection of impossible
preserve points. Keeping the smoke workflow separate prevents unnecessary
heavy CACE/Lean builds during rapid geometry iteration.


## Implemented modeler v0.3 — solid and mechanics prototypes

**Voxel solidification (validated approximation).**
Run:

```sh
python3 scripts/solidify_research_object.py \
  config/examples/research_object_demo.json \
  --candidate ring \
  -o candidate-watertight.obj \
  --report candidate-solid-validation.json
```

The new code replaces unjoined overlapping cylinder previews with a single
union-of-voxels surface, triangulated from exposed cube faces with welded
integer-grid vertices. It independently validates six-connected occupied cells,
oppositely oriented two-sided manifold edges, connected cycles around each
surface vertex, positive signed volume matching voxel occupancy, preserved
mounting-point inclusion, expanded obstacle/keep-out exclusion, and design-box
inclusion. It emits a watertight approximate solid with a deterministic hash and
voxel-derived volume/mass estimate; pitch is explicitly recorded. This is still
a *faceted voxel proxy*, not curved exact CAD or a fabrication certificate.
Insufficient resolution, surface nonmanifold topology, disconnected solids,
obstacle intrusion, missing preserved points, or exceeded resource ceilings
fail closed.

**Load-dependent 2D pin-jointed structural analysis.**
Run:

```sh
python3 scripts/evaluate_research_object_truss.py \
  config/examples/research_object_demo.json \
  config/examples/research_object_truss_load_case.json \
  -o candidate-truss-analysis.json
```

Explicitly defined pin supports, XY nodal loads, Young's modulus, and assumed
minimum strut diameter feed a small-displacement, 2D, linear axial-bar FEM.
The solver assembles symmetric axial stiffness, rejects singular mechanisms,
checks force equilibrium, and reports nodal displacements, axial stress/forces,
strain energy, compliance and residual. Declared stress/displacement limits
are evaluated rather than guessed. Eligible candidates receive a
mass–compliance–axial-stress Pareto shortlist; singular or failing designs
remain visible as rejections.

**Do not conflate the two representations.** The truss solver evaluates the
*centerline graph*, not a tetrahedral FEM of the voxelized solid. It cannot
certify bending, buckling, 3D stability, load-bearing joints, continuum stress,
real strength, or manufacture. In particular, the example's supports and
100 N load are illustrative assumptions, not a validated bracket duty cycle.

The dedicated GitHub-hosted workflow tests both paths and uploads:

- `cace-modeler.json`: graph candidates;
- `cace-modeler-preview.obj`: old overlapping-cylinder preview;
- `cace-modeler-watertight.obj` and `cace-modeler-solid-report.json`:
  independently checked voxel approximation;
- `cace-modeler-truss-report.json`: structural proxy and rejected candidates.

**Next qualification:** connect explicitly loaded geometry to a conforming
solid/beam FEM representation in CACE, verify stress and displacement against
an independent reference solve, run mesh-convergence and certified bounds, then
consider material/geometry optimization promotion. Do not label this work
"CACE-certified structural design" until those gates pass.
