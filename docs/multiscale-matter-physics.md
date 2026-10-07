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
