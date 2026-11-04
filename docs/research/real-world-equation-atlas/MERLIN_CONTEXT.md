# Merlin Context Package — Equation Atlas Research

## Source project and workflow
- Repository: Mannyspiro/expert-robot (private GitHub repository).
- Existing academic research capability: `python/merlin/academic_spider.py`, tests at `tests/test_academic_spider.py`, documentation at `docs/MERLIN_ACADEMIC_SPIDER_V01.md`.
- This contribution is isolated on branch `feat/merlin-real-world-equation-atlas-v01-20261104`, based on `feat/merlin-academic-spider-v01-20261103`.
- No protected-main changes are intended. Review through a PR before merging.

## Relevant Merlin capabilities and research themes
The current context includes: Shannon–Nyquist Signal & Aliasing Validator; MIT Ideonomy Simplex Combinator; AlphaFold/Evoformer and Ramachandran scoring; Internet Research & arXiv Literature Invariant Synthesizer; CAD/PCB/signal integrity; post-quantum cryptography; metamaterials/electromagnetism; biological growth/evolution; DNA transcription/genetics; spacetime/relativity.

User's broader research direction:
- Xenomathematics: discover alternate mathematical representations, operators, glyph systems, and coordinate systems without assuming human notation is fundamental.
- Multi-frame geometry: represent one object simultaneously in typed 2D/3D/4D/5D+ frames, with explicit projections, embeddings, mappings, and invariants.
- Geometric operators: glyphs can encode state transformations; notation is separate from the underlying operation.
- Research must separate established mathematics, computational conjectures, speculative models, and refuted ideas.
- CAD, simulation, visual explanations, and formal proofs should be integrated only where they add reproducible evidence.
- Math Kung Fu should teach intuition through shape, transformations, operators, equations, and structurally analogous problems, with concise explanations and staged difficulty.

## XMG model
Represent a shared object as:
`X = (O, {F_i}, {T_ij}, Ops, Inv)`
- O: underlying object/state.
- F_i: typed coordinate or representation frames.
- T_ij: explicit maps between frames.
- Ops: typed operations acting on objects or representations.
- Inv: invariants preserved under specified transformations.
Track frame conventions, units, dimensions, information loss, provenance, and whether a map is an active physical transformation, passive coordinate change, projection, or embedding.

## Model selection
No single equation is universally optimal. Compare models for each application on:
- predictive/fit error and external validity;
- computation, memory, and latency;
- model complexity and interpretability;
- uncertainty, sensitivity, and robustness;
- feasibility and hard constraint satisfaction.
A candidate objective is
`J(M)=w_pE_prediction+w_cE_compute+w_kE_complexity+w_uE_uncertainty+w_sE_sensitivity+w_rE_robustness+P_constraints`.
Justify weights; expose Pareto trade-offs; never hide unacceptable safety/physical constraint violations in a weighted score.

## Research pipeline
1. Ideonomy enumerates applications and candidate structures.
2. Academic Spider gathers literature with source provenance.
3. Equation Atlas normalizes equations, variables, units, assumptions, and regimes.
4. XMG maps representations and transformations across frames.
5. Simulation/CAD runs controlled numerical or physical experiments.
6. Independent verification checks derivations, dimensional consistency, tests, and reproducibility.
7. Lean formalizes mathematical claims where feasible.
8. Math Kung Fu converts supported results into visual lessons and exercises.

## Non-claims
This package records research direction and proposed outputs. It does not claim that a Merlin runtime was executed, a simulation was run, a CAD model was generated, a Lean theorem was proved, or literature was exhaustively reviewed in this commit.
