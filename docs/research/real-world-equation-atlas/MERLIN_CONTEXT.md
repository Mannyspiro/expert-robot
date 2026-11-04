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


## Phase 0.3 implementation update — 2026-11-04
- Avrea CI run 1271 (run ID 41837021534) completed successfully for the initial atlas checks and produced the reproducibility baseline artifact. This is execution evidence for that revision only; it is not an empirical validation or Lean qualification.
- The canonical entry schema now has an explicit per-variable `dimension` field so SI dimensional metadata is not discarded during normalization.
- `python/merlin/equation_atlas/normalize.py` migrates legacy entries 001–020 into canonical entries and validates each with JSON Schema Draft 2020-12. It preserves legacy conditions as explicit assumptions and source-register IDs as review-required citation records.
- All migrated entries are explicitly `UNVERIFIED`; a citation identifier is not treated as claim-level source validation.
- Added RWEA-021–030 for continuous/discrete state-space models, Kalman filtering, PID, LQR, serial-chain forward kinematics, Jacobians, numerical inverse kinematics, manipulator dynamics, and joint stiffness control.
- Added specialist references S22–S26: MIT Feedback Control Systems, Modern Robotics, MIT Underactuated Robotics, Åström–Murray Feedback Systems, and MIT Robotic Manipulation. Entry-level citations state the precise chapter or lecture coverage and preserve remaining application-specific limitations.
- The LQR cost matrices carry explicit time factors in their units; mixed revolute/prismatic robot coordinates and task-space angular/linear quantities remain typed rather than collapsed into one scalar unit.
- `python/merlin/equation_atlas/receipts.py` creates content-addressed evidence receipts binding the generated artifact to declared source files, code revision, command, and runtime metadata.
- CI run #1289 completed successfully on Avrea for the first 20 entries. It generated and schema-validated all 20 canonical entries, generated and validated the receipt, and published an artifact containing the baseline, canonical normalized tranche, and receipt. The artifact was downloaded and inspected; its receipt contains nine source hashes and all 20 entries are marked UNVERIFIED. A separate pending run is validating the combined 001–030 batch.

## Data and evidence rules
- Canonical entries are the typed source of truth; legacy JSON is migration input only until replaced.
- Preserve SI dimensions, coefficient dimensions, variable domains, and mixed-unit vector/matrix structure. Never silently coerce unknown units to dimensionless.
- Missing application details, boundary conditions, validity regimes, citations, and uncertainty remain explicit gaps, not invented facts.
- Keep independent evidence dimensions separate: source support, dimensional consistency, symbolic checking, computational reproduction, empirical validation, and formal verification.
- A generated receipt proves provenance and byte identity only within its declared scope. It does not establish scientific truth.
- A successful Avrea run is recorded against its exact commit and workflow run. Later changes require a new run before they are called tested.

## Next execution focus
1. Record Avrea run #1302 as successful for the 001–030 revision; run a new validation for the combined 001–040 revision and inspect its complete artifact bundle.
2. Extend receipts with test-output digests, container image digests, seeds/tolerances, and experiment-to-entry mapping.
3. Normalize entries 031–040 with primary PDE, electromagnetism, and numerical-method sources.
4. Expand dimensional checks and numerical convergence/sensitivity tests.
5. Execute separate Lean qualification and inspect exact theorem/axiom output.
6. Add XMG serialization and deterministic SVG exports from tested typed geometry.
7. Feed only appropriately supported entries into Math Kung Fu lessons.

The standing authority boundary remains: research and verification can produce evidence; promotion, merge, and permission changes remain approval-gated. Capability grows, authority never expands.


## Phase 0.4 research update — 2026-11-04
- Added RWEA-031–040: local conservation balance, heat conduction, advection-diffusion, linear wave, Laplace, Poisson, linear advection, incompressible Newtonian Navier–Stokes, differential Maxwell system, and Poynting energy balance.
- Added specialist source records S27–S29 from MIT OpenCourseWare PDE, numerical PDE, and electromagnetics courses, with entry-level crosswalks and explicit evidence boundaries.
- The new tranche is authored as canonical JSON and all ten entries remain UNVERIFIED. The compact source crosswalk does not replace a full primary-source derivation audit; RWEA-040 in particular needs a dedicated Poynting-theorem derivation and material-medium convention review.
- Updated the normalizer and schema tests to combine legacy 001–020 with canonical 021–030 and 031–040 batches into a 40-entry schema-validated output. CI now includes the 031–040 source file and emits the 001–040 normalized artifact.
- This work was authored through the GitHub repository integration on the Merlin research branch. The Avrea workflow is the repository's configured self-hosted runner; no separate direct Avrea session is claimed.

## Revised next execution focus
1. Complete Avrea CI validation for the 001–040 batch and inspect its evidence artifact and receipt.
2. Add executable dimensional checks for heat, wave, diffusion, Navier–Stokes, Maxwell, and Poynting equations, including component-wise vector/tensor units.
3. Add finite-volume conservation tests, heat/wave convergence tests, and electromagnetic energy-balance tests with deterministic seeds/tolerances where applicable.
4. Expand the source audit for Maxwell constitutive media, Poynting theorem derivation, fluid closures, and domain-specific boundary conditions.
5. Run the separate Lean qualification workflow; inspect exact theorem and axiom output before any formal status change.


## Avrea result clarification — 2026-11-04
- CI run #1302 (run ID `41839694953`) completed successfully for the 001–030 revision. Its downloaded artifact contains exactly 30 canonical entries, RWEA-001 through RWEA-030, all marked UNVERIFIED, along with a synthetic baseline and provenance receipt.
- The artifact ZIP SHA-256 is `699fa3156fc24ee108d38d02246b38ac994ae03941160715ff926a73493e02c7`.
- This successful run does not cover the later RWEA-031–040 tranche or the 40-entry normalizer/receipt-path changes. A separate run is required before reporting the 40-entry batch as validated.


## Phase 0.5 research update — 2026-11-04
- Added RWEA-041–050 covering Fourier series, continuous Fourier transform, convolution, LTI frequency response, DFT, Shannon-Nyquist sampling, uniform quantization, Shannon entropy, mutual information, and power spectral density.
- Added source register S30–S32 and an entry-level crosswalk to MIT OpenCourseWare signals/systems, sampling, and digital communications materials.
- Added canonical JSON tranche `NORMALIZED_ENTRIES_041-050.json`; every entry remains UNVERIFIED. The Shannon-Nyquist and quantization entries explicitly preserve ideal assumptions; the entropy/information entries distinguish discrete entropy from continuous differential entropy.
- Extended the canonical normalizer and schema test target from 40 to 50 entries. CI now includes the 041–050 input and is configured to emit the 001–050 combined artifact and evidence receipt.
- No Avrea run, numerical experiment suite, or Lean qualification for this 50-entry revision is yet claimed.

## Revised next execution focus
1. Run Avrea CI for the combined 001–050 revision and inspect the artifact and receipt.
2. Add executable spectral tests: Fourier/DFT round-trip, Parseval, convolution theorem, aliasing demonstrations, quantization error assumptions, entropy identities, and PSD normalization.
3. Add unit-aware metadata checks for amplitude, time, frequency, PSD, entropy, and logarithm base.
4. Audit the sampling theorem's strict band-limit condition and practical anti-alias filter assumptions.
5. Extend XMG with signal frames: time, frequency, scale, phase, probability, and information units as distinct typed frames.
6. Keep Math Kung Fu lesson generation limited to entries with source and validation gates satisfied.


## XMG signal and information frames — phase 0.5
Extend the typed multi-frame representation with signal-domain frames rather than mixing incompatible quantities in one coordinate vector:

- **Time frame** (F_t): time coordinate in seconds; sampling interval and clock reference are explicit.
- **Frequency frame** (F_f): frequency in hertz or angular frequency in rad/s; the conversion (\omega=2\pi f) is a typed map.
- **Amplitude frame** (F_a): physical signal amplitude with declared units and reference impedance/normalization where relevant.
- **Phase frame** (F_\phi): phase in radians, treated as dimensionless but with explicit periodicity and branch convention.
- **Probability frame** (F_p): normalized probability distributions; entries are dimensionless and sum to one.
- **Information frame** (F_I): entropy and mutual information in bits when logarithms are base 2; distinguish information units from physical SI dimensions.
- **Spectral-density frame** (F_S): PSD units are amplitude-squared per hertz or per rad/s, depending on convention; record one-sided/two-sided and angular/cyclic-frequency normalization.

Frame maps must record transform convention, normalization, finite-window assumptions, sample rate, aliasing policy, and whether a quantity is deterministic, random, or estimated. Do not silently compare amplitudes, power, probability, entropy, and spectral density as if they shared a unit system. Each transform edge should carry its inverse or information-loss status (e.g., finite sampling below the Nyquist condition is non-invertible without additional priors).

Suggested typed graph:
`TimeSamples --DFT(window, N, fs)--> ComplexSpectrum --MagnitudeSquared/Normalization--> PSD`
`JointDistribution --Marginalize--> Marginals --EntropyBase2--> Bits`
`JointDistribution --MutualInformationBase2--> Bits`

These are representation contracts and research directions, not claims that the current XMG runtime already implements them.


## Phase 0.6 research update — 2026-11-04
- Added RWEA-051–060: finite Markov chains, stationary distributions and detailed balance, Poisson processes, Brownian motion, Langevin SDEs, Fokker–Planck dynamics, Bayesian updating, linear Kalman filtering, Fisher information geometry, and Markov-jump entropy production.
- Added specialist source records S33–S36 and claim-level crosswalks to MIT stochastic-process, stochastic-calculus, nonequilibrium statistical-mechanics, and probability materials.
- Added deterministic synthetic checks for Markov stationarity, Brownian increment variance, Beta-Binomial posterior, scalar Kalman update, Ornstein–Uhlenbeck stationary variance, and entropy production on driven/equilibrium rings.
- Extended the canonical normalizer and schema tests to 60 entries; CI includes the new source tranche and stochastic experiment suite.
- All entries remain UNVERIFIED. In particular, Fisher information geometry and physical entropy production require specialist derivation and regularity/local-detailed-balance audits; course-level citations alone do not qualify them.

## XMG stochastic and probabilistic frames
Add typed frames for (1) sample space and event algebra, (2) probability measure and normalized distributions, (3) random-variable/state space, (4) transition kernel and generator, (5) time filtration/information, (6) path space, and (7) thermodynamic currents/entropy flow. Maps must distinguish a probability density from a probability mass, a sample path from an ensemble distribution, and dimensionless Shannon information from thermodynamic entropy in J/K. Record Itô versus Stratonovich convention and discrete versus continuous time explicitly. These are design contracts, not claims of runtime implementation.

Suggested typed paths:
`MarkovState --TransitionKernel(P)--> NextStateDistribution`
`SDE(drift,diffusion,interpretation) --FokkerPlanck--> ProbabilityDensity`
`StationaryDistribution + RateGenerator --ProbabilityCurrent--> EntropyProductionRate`


## Phase 0.7 — biological and collective systems
RWEA-061–070 extends the atlas into reaction-diffusion, Turing instability, cellular automata, logistic population growth, replicator dynamics, Wilson–Cowan neural populations, biological mutual information, Kuramoto synchronization, bond percolation, and self-organization observables.

Proposed typed XMG frames:
- **Field frame:** spatial coordinate, concentration/activity field, physical units, domain, and boundary condition.
- **Reaction frame:** species/state vector, kinetic map, conservation constraints, and parameter dimensions.
- **Lattice frame:** cell index, neighborhood, finite state alphabet, and update schedule.
- **Population-simplex frame:** frequencies, fitness map, normalization invariant, and mutation/noise extension.
- **Neural population frame:** excitatory/inhibitory activity, time constants, coupling, and activation map.
- **Oscillator-network frame:** phase, natural frequency, adjacency/weight matrix, coupling function, and order parameter.
- **Graph connectivity frame:** vertices, edges, ensemble, occupation probability, and component statistics.
- **Information-observation frame:** joint distribution, estimator, sampling window, bias correction, and units in bits.

Suggested typed transformations:
`ReactionState --DiffusionOperator(D,domain,boundary)--> SpatialFieldEvolution`
`PopulationSimplex --FitnessMap--> ReplicatorFlow`
`OscillatorNetwork --Coupling(K,A)--> PhaseField + OrderParameter`
`GraphEnsemble --BondOccupation(p)--> ComponentDistribution`

These are proposed contracts, not claims of an already implemented XMG runtime. Keep physical entropy, Shannon information, and dimensionless order parameters separate.


## Phase 0.8 — invasion, epidemics, and stochastic systems
- Added RWEA-071–080 for Fisher-KPP invasion fronts, Lotka-Volterra predator-prey dynamics, SIR epidemic dynamics, network metapopulations, Amari neural fields, chemical master equation, Gillespie SSA, RDME, adaptive coevolutionary networks, and generalized Lotka-Volterra communities.
- Added claim-level source records S48–S56. Explicit caveats include KPP wave-speed hypotheses, idealized neutral predator-prey cycles, incidence normalization in SIR, network mixing assumptions, neural-field coarse graining, propensity-model exactness, and RDME mesh/convergence limitations.
- Extended the canonical normalizer, schema regression test, Avrea artifact path, and evidence receipt inputs to RWEA-080.
- Added the proposed XMG cross-domain operator contract: reaction, diffusion, advection, graph coupling, jump process, phase coupling, neural convolution, and frame projection.
- Added a small declaration validator that checks operator input/output frame types and pipeline composition. This is a contract checker, not a physical simulator or a claim of production runtime support.
- Added CI tests for valid pipelines, exact frame matching, invalid frame types, and unknown operators.
- The 80-entry revision is authored but has not yet passed its own Avrea run. Prior run #1343 applies only to the exact 001–070 revision. All 80 entries remain UNVERIFIED.

## XMG cross-domain composition rules
A composed model should be a typed graph of operators, not a collection of unrelated one-off solvers:
- **Reaction** transforms local state using declared kinetic laws and stoichiometry.
- **Diffusion** transports a field under an explicit domain and boundary condition.
- **Advection** transports conserved quantities in flux form with explicit velocity and boundary flux.
- **Graph coupling** exchanges state across a declared adjacency or graph Laplacian; conservation depends on balanced flux convention.
- **Jump process** transforms discrete states and probability distributions using a generator or propensities, with row/column convention and state-space boundaries explicit.
- **Phase coupling** evolves periodic oscillator states with declared frequency, adjacency, and coupling function.
- **Neural convolution** applies a spatial kernel and activation function to a neural population field.
- **Frame projection** declares whether a map is an embedding, projection, active physical transformation, or passive coordinate change.

Composition is permitted only when output and input frame identifiers and required metadata match exactly. No implicit unit conversion is allowed. Each run should bind operator/version, input and parameter hashes, code revision, numerical method, tolerance, boundary conditions, and random seed when stochastic.


## Avrea verification update — 80-entry revision
- Avrea CI run #1354 (run ID `41842870640`) passed for PR head `d18959fe6d77dda863a98bea651ebd753c37d5c6`.
- All top-level CI steps completed successfully, including the atlas schema/dimensional/numerical test stage, artifact publication, engineering IR/CAD tests, CACE guardrails, Hermes/voice contracts, and independent smoke tests.
- Downloaded artifact ZIP SHA-256: `b751693229589025a011e89b3b01d4b42b3087a1fd6e4354808d19e4fca292c7`.
- Inspected normalized output: exactly 80 unique ordered entries RWEA-001–080; every entry remains `UNVERIFIED`.
- Normalized output SHA-256: `da3f9edba190fe667aecbae21eabfe422350e1be9a139fcba2bcea187236dc51`.
- Receipt SHA-256: `a39d9408dc258bdd47e4afeb4c2bb3b8a44d3d663535a5e0f531cfcdd2830271`; receipt contains 20 source/artifact hashes, including the new tranche, operator contract, validator, and operator tests.
- Receipt commit is the PR merge-ref snapshot recorded by the runner. CI success establishes test/reproducibility status for that exact snapshot, not empirical validity, scientific truth, or Lean proof success.


## Phase 0.9 — executable simulation core (first increment)
A first, deliberately small execution layer now exists:
- `explicit_euler`: common vector-state integration interface, shape/finite checks, full state trace, deterministic provenance metadata, and canonical run digest.
- `periodic_diffusion_rhs`: one-dimensional centered periodic Laplacian.
- `periodic_upwind_advection_rhs`: first-order upwind periodic transport for either velocity sign.
- `graph_exchange_rhs`: symmetric weighted-graph pairwise exchange with mass conservation implied by the graph Laplacian.
- `run_gillespie_ssa`: seeded direct-method continuous-time Markov jump simulation with stoichiometry, propensity validation, nonnegative-count enforcement, and trajectory digest.
- Synthetic tests cover diffusion/advection sum conservation, graph exchange conservation and nonnegativity, invalid RHS shape, SSA seeded reproducibility, and molecule-count conservation.
- CI executes the new test module and includes engine/test source in the evidence receipt.

Important limits:
- Explicit Euler is a baseline integrator, not an adaptive or stiff solver. Model authors must check the applicable diffusion stability bound, advection CFL bound, and graph-exchange step-size restrictions.
- The routines do not infer units, validate a model against nature, or guarantee stability for arbitrary parameters.
- SSA exactness is relative to the specified propensity functions and stoichiometric model.
- Every output is labeled synthetic and non-empirical. The current code revision awaits its own Avrea run; earlier run #1354 does not verify this increment.


## Phase 0.9 verification — Avrea run #1360
- Workflow run `41843498944` completed successfully for PR branch head `2854e92eafd36b5ad8de3f8ef6a6e4066c44738e`.
- All CI steps passed, including the equation-atlas test stage with the new simulation-engine tests and artifact publication.
- Artifact ZIP SHA-256: `39b32edc8e190143cf62cc0621860fe5a0bc8fa7aff8a798ab803409ed89daa3`.
- Evidence receipt SHA-256: `690efca64e79c3efb40bfd3e4b180118ad14ecb98cd233019d72cb6df9b22cd9`.
- Normalized 80-entry atlas SHA-256: `da3f9edba190fe667aecbae21eabfe422350e1be9a139fcba2bcea187236dc51`.
- Receipt's `git_commit` is the PR merge-ref snapshot `7cbaa1f40e6e2c0c5e5e787add3e85d552874e0f`; it is not the branch-head SHA. Receipt explicitly includes the simulation engine source and its test file.
- This pass verifies the declared tests and synthetic reproducibility only. It does not confer empirical validation, formal proof, or production solver status.


## Phase 0.9.1 — composed mathematical models
Built three first cross-domain model compositions on top of the shared integrator:
- **Reaction–diffusion:** local reaction RHS plus periodic diffusion RHS. The 1-D explicit diffusion condition `dt D/dx² ≤ 1/2` is enforced; reaction stiffness is not covered by this bound.
- **SIR:** susceptible/infectious/recovered transfers with closed-population conservation residual monitoring, initial-total validation, and a negative-compartment guard.
- **Lotka–Volterra:** coupled prey/predator growth, interaction, conversion, and mortality with positivity guard.
- CI adds model-level tests for composition, step-size restriction, population conservation, invalid initial totals, and reproducibility. The next Avrea run will verify this increment.


## Phase 0.9.1 verification — Avrea run #1366
- Workflow run `41844026188` passed for branch head `a1c551bde110cc72a93bf7a255adf3161930a57a`.
- The equation-atlas CI step passed with both simulation-engine and composed-model tests; all other workflow stages completed successfully.
- Artifact ZIP SHA-256: `a3f90c5c6fb5f66f4885bb83335b3939c141163069e691a7ad254bb9e63b0fc2`.
- Receipt SHA-256: `6d41c11d968e65a7306236f7181c6299a4bc166ac6247d4d124b7715e0107a81`.
- Normalized atlas SHA-256: `da3f9edba190fe667aecbae21eabfe422350e1be9a139fcba2bcea187236dc51`.
- Receipt contains 25 source/artifact hashes, including both model modules and their tests. Receipt merge-ref snapshot: `412d7bbb34fb2e1a0239660cf41b73afd13e2224`.
- This establishes the declared synthetic checks only; it does not establish empirical validity or formal proof.

## Phase 0.10 — MCFC / CAD / wiring geometry bridge
The engineering direction has been reframed as one canonical typed engineering object viewed through explicit coordinate frames, rather than independent CAD, PCB, and wiring drawings.

- MCFC is Merlin's virtual compute fabric, not a coordinate-frame system. It owns typed CPU, memory, and GPU resources; compute budgets; workload scheduling; expiring/revocable execution leases; and resource telemetry. This definition matches the prior MCFC virtual-fabric design.
- XMG owns the multi-coordinate-frame contract: world, enclosure, board, component-local, pin-local, harness, sensor, and optional thermal frames. The exact analogue for rigid frame placement is composition of transforms in SE(3); projections into 2D drawings are potentially lossy and must be labelled.
- CAD/wiring work is submitted to MCFC as a typed workload with explicit CPU/memory/GPU requirements, max wall time, compute budget, and required capabilities. Unknown hardware capacity remains unknown; no GPU is assumed from runner labels.
- The intended pipeline is: typed job definition → MCFC bounded lease/admission → Merlin CAD/wiring execution → CACE independent evidence verification → human approval for any qualification or promotion. A lease grants execution only, never engineering approval.
- The exact analogue for wiring is a graph/hypergraph embedded in 3D. Net endpoints are vertices; proposed conductor centerlines are polylines. Multi-terminal nets currently use a deterministic star topology.
- Added `python/merlin/wire_routing.py`: deterministic orthogonal 3D route proposals, conservative transformed AABB keep-outs, configurable geometric clearance assumption, path-length comparison, and explicit blocked/missing-geometry statuses. A global-Z overpass is a synthetic candidate only.
- Added `tests/test_wire_routing.py`: direct route determinism, AABB obstacle detour, missing geometry, multi-terminal topology, invalid clearance, and non-qualification label.
- Added `docs/research/MCFC_CAD_WIRING_INTEGRATION_V0.1.md`: MCFC virtual-fabric boundary, XMG frame contract, problem-to-mathematical-analogue map, CACE evidence gates, and engineering qualification requirements.
- Added the route test to the Avrea CI engineering test loop. The next run must be inspected against its exact head SHA before claiming this increment passed.

This is not yet a fabrication router. No wire gauge, ampacity, voltage-domain separation, creepage/clearance, impedance, thermal, EMI, bend radius, strain relief, connector, regulatory, or manufacturability checks are performed. AABB overlap is conservative broad-phase geometry, not exact solid collision. The generated polylines are not approved harness routes.

CACE integration boundary:
1. Merlin emits immutable project/frame/netlist/route artifacts and hashes.
2. CACE verifies schema, provenance, deterministic replay, declared constraints, and independent test receipts.
3. A separate qualified electrical/mechanical review must supply any required domain-specific sign-off.
4. Promotion remains approval-gated; no worker or model can self-authorize a fabrication or energized-hardware state.

Capability grows, authority never expands.

### Phase 0.10.1 — CACE route-evidence integration
- Added `python/merlin/route_evidence.py` to bind project, assembly, frame graph, route output, router version, and source commit into a deterministic SHA-256 receipt.
- Added a CACE-facing ledger ingest path that recomputes the receipt against the supplied project/assembly/route inputs before recording it as experiment evidence.
- Receipt status remains `not_qualified`; `promotion_authority` is always false. Ledger ingestion does not change hypothesis status.
- Added tests for deterministic binding, route-output tampering, assembly/frame changes, authority expansion, invalid source revision, and no-auto-promotion.
- Avrea CI engineering tests now include both route-planner and route-evidence tests. Verify the final run against its exact head SHA before treating the increment as passed.

### Phase 0.10.2 — Electrical / thermal / manufacturing proof-obligation layer
- Added `python/merlin/wire_qualification.py`: manufacturer-ampacity × supplied derating comparison; DC resistive voltage-drop estimate using explicit circuit-loop length; supplied insulation rating comparison; comparison to separately reviewed clearance requirement; lumped steady-state thermal estimate with temperature-corrected resistance; swept bend-radius and harness slack comparisons; 14 evidence gates.
- Missing conductor data, thermal correlation, swept bend geometry, standards applicability, tests or independent sign-off produce BLOCKED / REVIEW_REQUIRED results. The report never sets energized-use or manufacturing qualification true and never grants promotion authority.
- Added `python/merlin/wiring_exports.py`: logical Graphviz connectivity view, review-only wire schedule CSV and JSON schematic manifest. Outputs are deliberately labelled non-release and never invent wire specifications.
- Added tests for calculations, failed limits, absent evidence, non-certification and export labelling; added both suites to Avrea CI.
- Research roadmap ranks source-of-truth/provenance, electrical/protection review, thermal correlation, swept harness manufacturing geometry, EDA/CAD round-tripping, and independent verification.
- Standards families mapped for applicability review: IEC 60204-1 machinery electrical equipment; IEC 60664-1 insulation coordination; IPC/WHMA-A-620F harness manufacture/acceptance. Applicability is project-dependent and must be reviewed against the full normative editions.
- MCFC remains the virtual compute fabric; XMG coordinate frames remain a separate engineering representation contract.
