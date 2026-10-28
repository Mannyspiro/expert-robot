# Decisive evidence acquisition plan for residual physics tasks

Date: 2026-10-28  
Branch: `feat/residual-lean-audit-20261027`

## Guardrails

- Do not treat the toy script or this plan as a physical result.
- Keep `main` unchanged; no paid infrastructure or 32-vCPU runner.
- Separate exact theorem, numerical output, independent reproduction, and physical interpretation.
- The active Math Architecture Benchmark must finish before any edit under `formal/MathAI/**`, `formal/MathAI.lean`, or benchmark-triggering workflow paths; such edits can cancel that run.

## 1. Numerical FRG confirmation

**Decisive next step:** select one published flow system with complete beta/flow equations, regulator, truncation, normalization, and initial/boundary conditions; then independently implement the same system and compare at two resolutions or precision levels.

- Candidate methodological reference: [Optimization and stabilization of functional renormalization group flows, Phys. Rev. D 111, 096022 (2025)](https://doi.org/10.1103/PhysRevD.111.096022). It emphasizes regulator-dependent flow stability and numerical methods; it is not itself evidence for our target flow.
- A recent O(N)-gravity FRG paper reports that its data will be made available on request, so it is not a reproducible numerical target without obtaining those data and exact settings: [Annals of Physics (2026), DOI 10.1016/j.aop.2026.170545](https://doi.org/10.1016/j.aop.2026.170545).
- Current executable smoke test is `research/residual_physics/toy_baselines.py`: beta(g) = -g + g^2. The archived JSON shows the explicit-Euler error falls from about 3.29e-3 to 1.62e-3 when h is halved. This qualifies only the toy integration pattern.
- **Blocked physical inputs:** target paper/equations, regulator and truncation, parameter values, initial/boundary conditions, and reference data. Do not infer these from the toy.

## 2. Lattice Page-curve evaluation

**Decisive next step:** pin a finite lattice Hamiltonian, state preparation, cut convention, Hilbert-space truncation, and entropy calculation; run exact diagonalization for small sizes and compare with an independently computed reduced density matrix.

- Candidate published target: [Entanglement entropy of (2+1)-dimensional SU(2) lattice gauge theory on plaquette chains, Phys. Rev. D 110, 014505 (2024)](https://doi.org/10.1103/PhysRevD.110.014505). The paper reports Page-curve behavior in ground and excited states, but the target implementation must still pin its Hamiltonian, truncation, and state definitions from the paper/supplement before reproducing numbers.
- Exact smoke test currently in the repository: k Bell pairs crossing a bipartition give S = k ln 2. This validates units and a simple entropy identity only; it is not a dynamical Page curve or a lattice-gauge result.
- **Blocked physical inputs:** a concrete lattice model and truncation, exact state/circuit or Hamiltonian parameters, and reproducible entropy data.

## 3. Standard-Model-shifted fixed-point coordinates

**Decisive next step:** freeze the actual beta-function system and conventions before solving. Compute a candidate root numerically only after all couplings, Standard Model inputs, threshold treatment, regulator/scheme, and truncation are explicit; independently evaluate the residual and Jacobian.

- Relevant background method: [Functional renormalization for quantum gravity, Phys. Rev. D 106, 106022 (2022)](https://doi.org/10.1103/PhysRevD.106.106022), which derives flows and gives explicit examples. It does not, by itself, specify the user's intended Standard-Model-shifted system.
- Current exact smoke test is the affine system A x + b = 0 with A = [[2,1],[1,3]], b = [1,-1], whose exact root is (-4/5, 3/5). It demonstrates residual/Jacobian plumbing, not Standard Model coordinates.
- **Blocked physical inputs:** the precise model or paper, complete beta functions, parameter inputs, coordinate normalization, and stability sign convention. Fixed-point coordinates are often scheme/truncation dependent; do not present a toy root as a universal physical value.

## 4. Cosmological MCMC

**Decisive next step:** start with a small, public, frozen Planck PR3 baseline chain set and reproduce summaries/chain diagnostics from existing samples before attempting a new expensive likelihood run. Record exact chain root, companion parameter-name file, source checksum, burn-in, weights, and software versions.

- Official source catalog: [Planck PR3 ancillary data](https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/). It lists the baseline `CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00` product (about 63 MB) and larger alternatives.
- Sampler/likelihood implementation guide: [Cobaya Planck likelihood documentation](https://github.com/CobayaSampler/cobaya/blob/master/docs/likelihood_planck.rst). A likelihood rerun requires the specific likelihood data and configuration; existing chains alone can validate post-processing, not independently regenerate the posterior.
- Alternative indexed chain archive: [Planck 2018 chains dataset](https://huggingface.co/datasets/astro-legacy-archive/planck-2018-chains), derived from the full-grid archive. Use the original release as provenance authority and preserve parameter-name companions; the converted archive has headerless positional columns.
- Current MCMC smoke test targets a standard normal with a fixed seed and 50,000 retained samples. It checks basic sampler plumbing only, not cosmological inference.
- **Blocked physical inputs:** selected chain root/configuration and verified download/checksum; for a new run, likelihood release, priors, nuisance parameters, cosmological model, sampler settings, and convergence criteria.

## Current disposition

The four original physical task statuses remain `not_yet_formalized`. This is intentional: public papers provide plausible candidate targets, but the target-specific settings and reproducible numerical inputs have not yet been pinned. Next low-cost action is to select one exact published target per task, capture its equations/settings and source checksums, then implement a small independent reproduction. No claim is promoted until the evidence exists.
