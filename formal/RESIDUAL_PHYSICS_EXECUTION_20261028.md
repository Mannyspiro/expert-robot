# Residual physics execution report — 2026-10-28

## Operating decision
- No new training, architecture benchmark, or training-like run is being launched.
- Work is isolated on branch \`research/residual-physics-execution-20261028\`, not the \`feat/**\` branch pattern used by the external-runner bridge.
- \`main\` remains unchanged.
- The CACE bridge run \`40616981684\` timed out waiting for external evidence. There is no returned OCI execution record, so no CACE regression pass is claimed.

## 1. Lattice Page-curve task: small-N implementation check achieved
Source target: Ebner et al., *Phys. Rev. D* 110, 014505 (2024), Eq. (2), “Entanglement entropy of (2+1)-dimensional SU(2) lattice gauge theory on plaquette chains.”

Artifacts:
- \`research/residual_physics/lattice_small_n_check.py\`
- \`research/residual_physics/lattice_small_n_check_20261028.json\`

The script implements the paper's transcribed Ising-limit periodic spin-chain Hamiltonian with a stated dimensionless parameter point \`g2a=1.6, a=1\`, then checks Hermiticity, eigenpair residuals, eigenvector norms, reduced-density trace, PSD up to roundoff, and pure-state subsystem entropy symmetry.

Local runs:
| Sites | Hilbert dimension | Max eigenpair residual | Max trace error | Result |
|---:|---:|---:|---:|---|
| 3 | 8 | 1.92e-15 | 3.33e-16 | pass |
| 4 | 16 | 3.85e-15 | 1.55e-15 | pass |
| 5 | 32 | 5.95e-15 | 1.22e-15 | pass |
| 6 | 64 | 6.43e-15 | 8.88e-16 | pass |

A first odd-site test exposed an indexing bug in the complementary subsystem entropy calculation. The subsystem-index mapping was corrected and the 3–6 site sweep then passed. This is a useful regression finding.

**Still not solved:** this spin-site partition is not automatically the paper's gauge-invariant link-cut entropy; this is not the published N=17 benchmark, not higher-representation convergence, and not evidence about black-hole evaporation or a continuum limit. The original physical task remains unqualified.

## 2. FRG numerical confirmation: target method clarified, physical reproduction still blocked
A relevant methodological paper is Zorbach, Stoll, and Braun, “Optimization and stabilization of functional renormalization group flows,” *Phys. Rev. D* 111, 096022 (2025), DOI 10.1103/PhysRevD.111.096022. It studies regulator-dependent numerical stability in a scalar-field local-potential approximation, including a Kurganov–Tadmor finite-volume formulation and LSODA-based time stepping.

This is a method target, not a substitute for the user's intended physical flow. The remaining requirements are the exact flow system, regulator, truncation, initial potential, grid, and reference data. The existing scalar \`beta(g)=-g+g^2\` checks remain toy-only. No claim of a physical FRG confirmation is made.

## 3. Standard-Model-shifted fixed point: input specification remains the blocker
A unique coordinate result cannot be computed responsibly without the coupled beta functions, RG scheme/regulator, truncation, coupling normalization, Standard Model inputs and uncertainties, threshold treatment, and stability sign convention. Generic quantum-gravity FRG equations do not determine which system was intended.

The scalar rational affine-root existence theorem is now included in \`formal/MathAI/Audit.lean\` and registered in \`formal/theorem_registry.json\` on the research branch. It proves only a generic one-variable algebra fact. It does not prove a Standard Model or quantum-gravity fixed point.

## 4. Cosmological MCMC: official chain archive identified, independent post-processing not yet executed
Official Planck PR3 archive index:
https://irsa.ipac.caltech.edu/data/Planck/release_3/ancillary-data/cosmoparams/

Selected baseline archive:
\`COM_CosmoParams_base-plikHM-TTTEEE-lowl-lowE_R3.00.zip\` (listed at approximately 62 MB). The web index is accessible, but the archive was not successfully retrieved into the execution environment in this run. Therefore no checksum, chain inventory, weighted marginal reproduction, ESS, or convergence diagnostic is claimed.

The next bounded action is to retrieve the archive through an accessible download path, verify its checksum, inventory parameter names and weights, then independently recompute weighted summaries from the existing chains. That would validate post-processing only; a new likelihood run requires a pinned Planck likelihood, priors, nuisance parameters, model, and sampler configuration.

## What this says about unified field theory
These four tasks are residual validation work, not a complete proof program for a unified field theory. A genuine proof requires a precise candidate theory: field content, action or axioms, symmetries, gauge structure, quantization/regularization choices, equations of motion, and explicit theorem statements linking the sectors. None can be inferred uniquely from the four task labels alone.

Current honest status:
- Lattice: small-N numerical implementation checks pass; physical reproduction not established.
- FRG: method literature identified; target physical flow not pinned.
- SM-shifted fixed point: blocked by missing equations and conventions.
- Cosmological MCMC: official archive identified; chain retrieval and analysis pending.
- Unified field theory: **not proved**; no claim of unification, empirical confirmation, or formal derivation is made.
