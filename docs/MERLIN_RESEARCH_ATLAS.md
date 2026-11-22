# Merlin Research Atlas and Methodology

**Snapshot:** 2026-11-16  
**Companion document:** [MERLIN_MASTER_CONTEXT.md](./MERLIN_MASTER_CONTEXT.md)

This atlas records the research fields and methods the user has asked Merlin to support. It is a scope map and research program, not a claim that all listed capabilities are implemented.

## A. Research principles

1. **Public-source-first:** use publicly available resources; ingest public-domain books and open scientific/technical resources where licensing permits.
2. **Source before synthesis:** preserve exact source identity, version, date, license, digest and locators.
3. **Normalize before comparing:** define variables, units, assumptions, domains, boundary conditions, coordinate frames and operational definitions.
4. **Enumerate before choosing:** use Ideonomy to generate candidate explanations, models, primitives, relationships and experiments.
5. **Induction and deduction:** discover patterns empirically, then derive and prove consequences where possible.
6. **Skepticism:** challenge assumptions, bias, confounders, fallacies, selection effects, missing controls and overclaiming.
7. **Reproducibility:** pin tool versions, data, seeds, precision, solver settings, environments and output digests.
8. **Falsifiability:** record what observation, counterexample or experiment would weaken or refute a claim.
9. **Independent verification:** use CACE and formal/numerical gates appropriate to the artifact.
10. **Epistemic humility:** distinguish established results, evidence-supported models, unresolved questions, hypotheses and speculative exploration.

## B. Domain map

### 1. Pure and applied mathematics
Algebra; number theory; combinatorics; discrete mathematics; linear and abstract algebra; calculus; real and complex analysis; functional analysis; differential equations; PDEs; optimization; numerical analysis; probability; statistics; Bayesian inference; stochastic processes; information theory; graph theory; topology; algebraic topology; homology and homotopy; geometry; category theory; type theory; formal methods; control theory; dynamical systems; operations research; tensors and matrix methods.

### 2. Mathematical modelling and computational science
Conservation laws; heat/wave/Maxwell equations; reaction-diffusion; state-space and Kalman filtering; Fourier/signal processing and Shannon–Nyquist; least squares; eigenmethods; finite-element methods; networks; multiscale models; sensitivity and uncertainty analysis; parameter estimation; numerical stability; optimization under constraints.

### 3. Physics and spacetime
Mechanics; continuum mechanics; thermodynamics; electromagnetism; fields and waves; relativity; spacetime geometry; Minkowski invariants; quantum theory and foundations; fluid dynamics; materials and multiscale physics. Require dimensional consistency, domains of validity and empirical comparison.

### 4. Chemistry, materials and biochemistry
Physical/organic/inorganic/analytical chemistry; reaction kinetics; thermodynamics; molecular structure; transport; protein structure and interaction; DNA transcription; biochemical pathways; materials and metamaterials; property prediction; reaction networks. Computational structural scores must not be mistaken for clinical evidence.

### 5. Biology and evolution
Genetics; molecular/cell/systems biology; evolution; ecology; developmental biology; morphogenesis; biological growth; protein structure; information processing in living systems. Non-carbon life and nonhuman consciousness are exploratory questions whose speculative status must remain explicit.

### 6. Engineering
Mechanical, electrical, electronics, controls, robotics, systems and software engineering; CAD assemblies; geometry and constraints; engineering IR; wiring and netlists; PCB relationships; safety, thermal and manufacturing analysis; FEM; ngspice and other reproducible simulation adapters.

### 7. Computer science and AI
Algorithms/data structures; languages/compilers; type systems; databases; distributed systems; event sourcing; reliability; AI/ML; model evaluation; inference; multimodal generation; agents; retrieval; knowledge graphs; privacy/security; sandboxing; supply-chain provenance; formal verification; software testing and reproducible builds.

### 8. Economics, finance, statistics and risk
Optimization, econometrics, forecasting, time series, Bayesian inference, risk and public-finance datasets may be useful applied domains. Preserve data vintages, assumptions, causal limitations and out-of-sample tests. Keep separate from election/voting-system infrastructure and separate from Titan security research unless independently scoped.

### 9. History, philosophy and pedagogy
History of mathematics/science/engineering; biographies and intellectual context of pioneers; philosophy of scientific explanation and mathematical foundations; problem-solving pedagogy; mathematical communication; computational thinking; learning science.

### 10. Literature and cross-disciplinary synthesis
Systematic literature search; source quality; citation graph; methods and dataset comparison; definition reconciliation; invariant discovery; contradictions; replication and evidence grading. The arXiv literature invariant synthesizer is a named skill concept.

## C. Xenomathematics and XMG program

### Xenomathematics
Explore mathematical systems that do not assume familiar human symbols or conventions. Candidate research directions:
- Operations represented as glyphs, geometry or embodied procedures.
- Composable operator collections and alternative algebraic syntax.
- Nonhuman/alien notation and possible cognitive constraints.
- Biological mathematical representation.
- Formal comparison of alternative symbol systems by expressiveness, compositionality, invariants, computability and learnability.

Do not assume alien mathematics or nonhuman cognition exists in any specific form. Treat candidate systems as constructed formal objects or speculative hypotheses until evidence supports stronger claims.

### XMG (multi-frame geometry and representation)
- Represent one point/object across 2D, 3D, 4D, 5D and higher-dimensional coordinate systems.
- Support Cartesian, polar, cylindrical, spherical, projective and custom frames.
- Connect real/complex/quaternion/octonion/Clifford/matrix/tensor representations.
- Model basis changes, coordinate transforms, invariants and information loss.
- Treat equations, matrices and operators as manipulable geometric objects.
- Create glyph algebra and a compiler from symbolic/glyphic expression to typed mathematical IR.
- Generate multi-frame visualization and CAD-compatible outputs.
- Require formal transform contracts and testable invariants.

### Candidate engines
- Ideonomy Engine.
- XMG Glyph Compiler.
- Coordinate/Algebra/Geometry Engines.
- Invariant Discovery Engine.
- Equation Atlas.
- Visualization/CAD bridge.
- Lean formalization and CACE evidence bridge.

## D. Real-World Equation Atlas

Each entry should include:
- Canonical equation/model and alternate forms.
- Field, use case and source references.
- Symbol dictionary, dimensions and units.
- Assumptions and boundary/initial conditions.
- Domain of validity and known limitations.
- Derivation or proof status.
- Numerical/symbolic checks.
- Experimental data and reproducibility metadata.
- Counterexamples and falsification conditions.
- Related equations, invariants, coordinate frames and applications.
- Learning explanation and exercises, only after correctness gates.

Previously identified priority applications include robotics, CAD, biology, chemistry, materials, finance/statistics/risk and scientific computing.

A prior atlas v0.2 was reported to include normalized entries 001–020, source crosswalk, Python checks/experiments, Lean candidates not compile-confirmed, XMG contracts/examples/frame graph, lessons and CI wiring. Entries 021–100, specialist sources, full checks, CI/Lean execution and interactive XMG views were unresolved at that time. Revalidate the actual branch and artifacts before treating this as current implementation.

## E. Research workflow templates

### Hypothesis template
- Question and scope.
- Definitions and operationalization.
- Source evidence and exact locators.
- Candidate explanation.
- Competing explanations.
- Assumptions and dependencies.
- Predicted observations.
- Falsification/counterexample criteria.
- Experiment/proof design.
- Uncertainty, bias and limitations.
- Verification requirements.

### Equation/model template
- Canonical expression and symbol table.
- Units and dimensional checks.
- Assumptions and domain.
- Derivation and cited source.
- Baseline/alternative models.
- Numerical stability and sensitivity.
- Reproducible experiment metadata.
- Formal proof or explicit non-proof status.
- Empirical validation and limitations.

### Literature synthesis template
- Search strategy and date.
- Inclusion/exclusion criteria.
- Source/version/licence.
- Methods, data and population.
- Definitions and assumptions.
- Main claims and evidence types.
- Agreement, contradiction and gaps.
- Replication status.
- Confidence and unresolved questions.

### Engineering design template
- Requirements and constraints.
- CAD/IR and component identities.
- Materials, tolerances and interfaces.
- Electrical/mechanical/thermal constraints.
- Simulation and solver configuration.
- Safety/manufacturing standards and revisions.
- Test fixtures and measured results.
- Artifact lineage and independent review.

## F. Named research/learning skills from prior context

Previously mentioned built-in skill concepts include:
- Shannon–Nyquist validator.
- MIT Ideonomy Simplex.
- AlphaFold/Evoformer Ramachandran scorer.
- arXiv literature invariant synthesizer.

Other named research/capability areas include CAD/PCB, metamaterials, biological growth, DNA transcription, spacetime/relativity, XMG multi-frame representations and Math Kung Fu. The existence of a skill name or manifest entry is not evidence of a qualified implementation.

## G. Research quality gates

A candidate research result must not be described as established unless the evidence justifies it:
- Source identity and locator verified.
- Definitions, units and assumptions explicit.
- Alternative explanations considered.
- Data/method reproducible.
- Appropriate numerical/statistical checks run.
- Formal proof compiled when a theorem is claimed.
- Counterexample search bounded and documented.
- Independent CACE receipt obtained where required.
- Limitations and domain of validity stated.

A citation is not proof; a model score is not probability unless calibrated; a numerical result is not a theorem; a successful test suite does not establish real-world validity; and a reviewer opinion does not independently verify the artifact.
