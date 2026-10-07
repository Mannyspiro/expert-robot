# Multiscale Matter + Physics Research Layer

CACE should be able to reason across a continuous stack:

```
Atom
-> Bond
-> Molecule
-> Polymer / Crystal / Biomolecule
-> Microstructure / Metamaterial Unit Cell
-> Bulk Material
-> Device / Assembly
-> Experiment
-> Measured or Simulated Observables
-> Residual / Error Bound
-> Verified Research Result
```

## Matter graph

The Research Matter Graph represents chemistry and structure explicitly.

Examples:

- metals: atoms -> crystal unit cell -> lattice -> grain -> phase -> alloy/composite;
- DNA/RNA: atoms -> nucleotides -> sequence -> secondary/tertiary structure;
- proteins: atoms -> amino acids -> chain -> folded structure -> complexes;
- metamaterials: constituent material -> unit-cell geometry -> lattice -> effective medium;
- computational biomachines: molecular/structural components -> interfaces -> coupled mechanical/energetic model.

Novel biological-machine work remains simulation-first and does not emit wet-lab construction instructions.

## Metamaterials

Metamaterials are represented at two coupled levels:

1. constituent physics/chemistry;
2. geometric unit-cell topology.

CACE can optimize for emergent properties such as:

- effective permittivity/permeability;
- negative or near-zero index regimes;
- anisotropy;
- acoustic impedance;
- phononic/photonic band gaps;
- mechanical auxetic response;
- stiffness-to-weight;
- thermal transport;
- wave steering;
- resonance placement;
- topological edge/interface modes where the model supports them.

The generator may mutate both material composition and geometry, but every
candidate must survive homogenization validity checks and, when relevant,
full-wave/unit-cell simulation rather than relying only on an effective-medium
approximation.

## Physics experiment engine

CACE should also generate experiments, not just objects.

A physics experiment is modeled as:

```
hypothesis
-> apparatus
-> matter/object samples
-> sources/fields
-> boundary conditions
-> parameter sweep
-> observables
-> controls
-> simulation
-> uncertainty model
-> adaptive next experiment
```

Supported research families can include:

- mechanics / elasticity;
- acoustics;
- electromagnetism;
- optics;
- heat transfer;
- fluid dynamics;
- condensed matter;
- metamaterials;
- coupled multiphysics;
- bounded quantum-model research;
- mathematically specified relativity models.

## Adaptive experiment loop

Expert Robot should rank the next experiment by expected information gain:

```
candidate design
-> simulate
-> estimate uncertainty
-> predict distinguishability between hypotheses
-> select experiment
-> run virtual/physical test
-> update model
-> repeat
```

This reuses the existing Expert Robot philosophy: the proposer does not certify
its own idea, expensive work is bounded, and verification is independent.

## Commercial implementation policy

All core geometry, chemistry-structure, metamaterial, and experiment interfaces
must remain compatible with the repository's commercially permissive dependency
policy.

Public NASA workflows may inspire abstractions, but restricted or NOSA-licensed
software is not copied into the core.

## Implemented computational matter modeler (October 2026)

The initial matter graph is now executable for **bounded organic small
molecules** and **periodic crystal geometry**, using the same existing
`research_matter_graph.schema.json` representation.

### Molecular candidate route (RDKit 2026.3.6, BSD-3-Clause)

```sh
python3 scripts/generate_molecular_matter.py --smiles CCO --id ethanol-demo \
  --conformers 3 --seed 1729 \
  --matter-graph ethanol.matter.json \
  --metadata ethanol.metadata.json --molblock ethanol.mol
```

The routine sanitizes SMILES, limits chemical scope to a single connected
organic molecule with at most 48 heavy atoms, rejects unassigned stereocenters,
radicals, unsupported atoms, embedding failures and force-field unavailability.
It generates reproducible ETKDGv3 candidate conformers, selects the lowest
successful MMFF94/UFF local minimization, screens gross nonbonded overlaps,
and checks exported MolBlock graph consistency. Reported energies are
**approximate force-field energies, not quantum-mechanical free energies,
synthesizability, or evidence of a stable chemical species**. Positions are
in ångströms and are recorded with units and model provenance.

### Crystal/unit-cell candidate route (stdlib)

```sh
python3 scripts/validate_crystal_matter.py \
  config/examples/crystal_cscl_unit_cell.json \
  --report cscl.geometry.json --cif cscl.geometry.cif \
  --matter-graph cscl.matter.json
```

Checks right-handed/nonsingular lattice, finite in-cell fractional positions,
distinct periodically equivalent sites, and obvious short-distance clashes in
a bounded neighbor-image search. Exports an explicit **P1** crystal CIF and
typed Matter Graph with a crystal cell containing atomic sites. The program
does not infer a crystallographic space group or validate electronic,
thermodynamic, phononic, or defect stability. Large/skewed cells, periodic
bonding and serious atomistic simulation remain unimplemented.

### Evidence and production status

`config/matter_manufacturing_readiness_policy.json` and
`scripts/evaluate_matter_readiness.py` enforce the distinction between
computational designs, qualified property calculations, characterized lab
samples, and repeatable production. They **never** authorize physical
production: external evidence is not authenticated in this application,
even when it looks complete. The source files produce no synthetic route,
laboratory instructions or real atoms.

The independent `Molecular Matter Modeler Tests` workflow uses a
GitHub-hosted runner (no Avrea credits) to run the molecule, crystal and
readiness tests, and produces portable model data. Future qualification
requires independent thermodynamics/electronic-structure solvers with
convergence controls; reliable predictions for targeted properties; applicable
safety and intellectual-property review; externally performed laboratory
characterization; and reproducible process/QC qualification.

### Bounded quantum electronic-structure baseline (PySCF)

The separate `scripts/evaluate_molecular_quantum.py` route consumes the typed,
RDKit-sanitized molecular Matter Graph and computes a **restricted Hartree-Fock
closed-shell** reference using STO-3G and 6-31G basis sets. Its scope is limited
to neutral, even-electron single molecules with 2–16 explicit atoms, supported
elements and recorded Ångström units. A failing SCF, unsupported electronic
state, unknown unit, or invalid input is rejected. Output records SCF
convergence, total Hartree energies, basis-function counts, graph hash,
basis sensitivity and PySCF version.

```sh
python3 scripts/evaluate_molecular_quantum.py water.matter.json \
  -o water-rhf-baseline.json
```

The `Molecular Quantum Baseline` GitHub-hosted workflow pins PySCF 2.14.0
(Apache-2.0) and RDKit 2026.3.6 (BSD-3-Clause), tests a computational
water model and uploads its inputs and results. It is not a proof of
basis-set convergence, correlated electron energetics, equilibrium geometry,
vibrational stability, chemical yield, synthesis feasibility, or thermodynamic
stability. Real production still requires rigorous cross-model verification
and independent measurement; no wet-lab operations are performed here.
