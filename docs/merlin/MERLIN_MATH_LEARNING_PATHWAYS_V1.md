# Merlin Mathematics Learning Pathways v1

**Status:** architecture and implementation plan; not a production qualification.
**Canonical inputs:** `docs/research/merlin-mathematical-idea-catalog.v1.json`, `docs/merlin/MERLIN_MATH_FOUNDATIONS_COURSE_V1.json`, and the tenant-scoped Merlin Learning service.

The machine-readable mapping is maintained in `docs/merlin/MERLIN_MATH_LEARNING_PATHWAYS_V1.json`. It maps all 57 current catalog ideas into the three pathways and labels whether a lesson reference already exists. `scripts/merlin_math_pathways_validate.py` checks catalog identity, idea coverage, pathway membership, lesson-reference consistency, and prerequisite integrity; the LMS evidence workflow runs this validator.

## Current curriculum artifacts

The canonical catalog currently contains 57 mathematical ideas, with 26 catalog lesson references. The authored course manifests now cover:
- **Mathematics foundations:** whole-number patterns, variables, divisibility, primes, loops, Euclid's proof, and counterexamples.
- **Logic and discrete mathematics:** quantifiers, sets and relations, and graphs and trees.
- **Algebra and functions:** patterns, variables, sets, equations and inequalities, function composition, and inverse mappings.

The lesson backlog contains 31 additional review-gated blueprints for ideas without a catalog lesson reference. These are authoring specifications, not completed lessons. A lesson reference is only promoted after its manifest, exercise, rubric, pathway coverage, and validator are present. The LMS evidence workflow checks the catalog graph, three-path mapping, and backlog's epistemic gates.

## Product objective

Build one adaptive mathematics environment with three mutually reinforcing routes:

1. **Mathematician** — discover structure, form conjectures, search for counterexamples, prove, generalize, and formalize.
2. **Mathematics programmer** — translate mathematical objects into data structures, algorithms, exact/numerical implementations, tests, and reproducible experiments.
3. **Computational hacker** — decompose unfamiliar problems, build the smallest useful experiment, debug, test edge cases, measure, improve, and explain.

These are learning emphases, not separate silos. Every learner can move between them, and the same mathematical idea should be encountered in more than one representation.

## Shared learning cycle

Every substantial concept should support this cycle, in an order that delays formal notation until the learner has a reason to need it:

1. **Curiosity hook:** a concrete puzzle, visual pattern, historical problem, engineering question, or learner-selected interest.
2. **Concrete model:** objects, examples, manipulable values, or a small working program.
3. **Observation:** compare cases and state what changes and what stays invariant.
4. **Conjecture:** write a precise, bounded claim with declared domain and assumptions.
5. **Adversarial test:** search boundary cases and counterexamples; distinguish a finite test from a proof.
6. **Abstraction:** introduce symbols, definitions, diagrams, functions, or data structures only when they compress or clarify the observed pattern.
7. **Justification:** explain why the claim follows; identify hidden assumptions and alternative cases.
8. **Proof or experiment:** use a mathematical proof, Lean, exact computation, numerical simulation, or bounded search as appropriate. Label the epistemic strength of each result.
9. **Implementation:** translate the idea into an algorithm, program, model, or visual artifact where useful.
10. **Transfer and reflection:** solve a changed problem, explain the strategy, identify remaining uncertainty, and schedule retrieval.

A computation can disprove a universal claim by finding a valid counterexample. A finite run without a counterexample is not a universal proof.

## Pathway progression

### A. Mathematician

| Stage | Learner work | Exit evidence |
|---|---|---|
| Pattern sense | Notice invariants, regularity, and exceptions | Accurate observations over varied examples |
| Definitions | State domains, objects, and quantifiers | Definitions distinguish near-miss cases |
| Conjecture | Formulate a claim from examples | Claim is precise and falsifiable |
| Counterexample | Search edge cases and repair claims | Counterexample is valid and scope is explained |
| Proof | Build direct, contrapositive, contradiction, induction, or construction proofs | Complete argument with assumptions and logical dependencies |
| Generalization | Identify which assumptions are essential | Correctly generalizes or gives a boundary |
| Formalization | Encode selected claims in Lean 4 | Pinned compiler receipt and no unverified proof placeholders |

### B. Mathematics programmer

| Stage | Learner work | Exit evidence |
|---|---|---|
| Representation | Map an idea to variables, tables, graphs, vectors, or symbolic forms | Correct translation between at least two representations |
| Algorithm | Specify inputs, outputs, state, update, and termination | Clear algorithm and termination argument |
| Implementation | Write readable, typed code | Reproducible implementation |
| Testing | Unit, property, boundary, and adversarial tests | Tests include positive and negative controls |
| Exact/numerical methods | Choose rational/exact or floating-point computation deliberately | Precision, solver, seed, and assumptions recorded |
| Analysis | Compare correctness, complexity, stability, and error | Measured comparison with a baseline |
| Formal bridge | Relate program invariants to mathematical claims | Proof or evidence identifies exactly what is established |

### C. Computational hacker

| Stage | Learner work | Exit evidence |
|---|---|---|
| Decomposition | Break a large task into small questions | Explicit dependency and uncertainty map |
| Minimum experiment | Build the smallest discriminating test | Experiment answers a named question |
| Debugging | Reproduce and isolate failure | Minimal failing case and root-cause explanation |
| Edge-case attack | Generate boundary, malformed, and adversarial inputs | Counterexamples are retained as regression tests |
| Measurement | Profile runtime, memory, precision, and failure rate | Reproducible measurements with environment metadata |
| Improvement | Optimize without changing semantics silently | Before/after benchmark and correctness checks |
| Explanation | Teach the method and limitations | Another learner can reproduce and critique the result |

## Shared curriculum spine

The current canonical course supplies the first seven-objective foundation. Expand from it through prerequisite-linked modules rather than a single rigid grade-level sequence.

| Domain | Canonical idea families | Main connections |
|---|---|---|
| Arithmetic and number theory | Whole-number patterns, divisibility, primes, Euclid's proof | Algorithms, induction, modular arithmetic, cryptography literacy |
| Algebra and functions | Variables, expressions, equations, functions, sequences | Programming state, graphs, modeling, calculus |
| Logic and proof | Definitions, quantifiers, implication, contradiction, induction | Lean, program invariants, counterexamples |
| Discrete mathematics | Sets, relations, graphs, counting, recurrence | Algorithms, data structures, complexity |
| Geometry and representation | Coordinates, transformations, symmetry, projective and polyhedral geometry | CAD, computer graphics, robotics |
| Trigonometry and complex numbers | Angles, periodicity, complex plane, rotations | Signals, transforms, control, higher-dimensional representations |
| Linear algebra | Vectors, matrices, linear maps, eigenstructure, invariants | Geometry, data science, numerical methods, physics |
| Calculus and analysis | Limits, derivatives, integrals, series, differential equations | Optimization, dynamics, simulation |
| Probability and statistics | Random variables, distributions, inference, uncertainty, experimental design | Machine learning, finance, scientific reasoning |
| Numerical and computational mathematics | Error, stability, root finding, ODE solvers, optimization | Reproducible labs, engineering, scientific computing |
| Applied and visual mathematics | Fractals, Fourier representations, tessellations, data visualization | Art, sound, image, physical design |
| Research mathematics | Conjecture graphs, proof obligations, open questions, null models | Ideonomy, formal verification, research workflow |

The idea catalog currently contains 57 typed idea records, including a newly added core spine for logic, sets, graph theory, equations, functions, modular arithmetic, complexity, linear algebra, calculus, probability, statistics, numerical analysis, differential equations, and optimization. Use it as a seed graph, not as a complete syllabus. Before publishing a module, validate every prerequisite against the canonical catalog and label each node as taught, planned, research-only, refuted, or unresolved. Research-only and unresolved ideas must not be presented as established facts.

## Ideonomy and useful lacuna search

For each domain, enumerate candidate ideas by crossing:
- mathematical object × representation × operation;
- theorem × assumptions × counterexample class;
- algorithm × invariant × complexity/error model;
- learner misconception × prerequisite × diagnostic task;
- historical method × modern formalization;
- application domain × measurable observable × falsifiable model.

Rank candidates by prerequisite leverage, transfer value, teachability, evidence quality, and implementation cost. Treat unusual graph gaps as prompts for investigation, not proof of novelty. Keep only combinations with coherent definitions, useful applications, and a path to testing.

High-value cross-domain learning patterns to develop:
- **Representation translation labs:** one object rendered as a diagram, equation, data structure, and program, with explicit maps between them.
- **Conjecture repair labs:** a learner's claim is challenged by edge cases, then refined into a true statement with explicit scope.
- **Proof-to-program bridges:** a theorem's invariant becomes a program invariant; compare the formal statement with executable tests.
- **Error-to-prerequisite diagnosis:** classify an error (definition, representation, algebra, logic, algorithm, precision) and recommend the missing prerequisite rather than repeating the whole lesson.
- **Multi-scale modeling:** connect a concrete local pattern to a global invariant, while stating where the analogy breaks.
- **Evidence-strength comparison:** compare observation, finite search, exact computation, numerical evidence, informal proof, Lean proof, and independent CACE verification without collapsing them into one score.

## Historical mathematics as a teaching resource

Historical profiles should explain the problem a mathematician was trying to solve, the representations and tools available at the time, the reasoning strategy, and how later mathematics revised or generalized the result. Use primary sources when accessible and distinguish historical context from modern reconstruction.

Initial sequence:
- **Euclid:** definitions, construction, divisibility, and proof structure.
- **Archimedes:** exhaustion, approximation, and bounding arguments.
- **Al-Khwarizmi:** systematic algebraic procedures and the history of algorithmic thinking.
- **Descartes and Fermat:** coordinate geometry and translation between algebraic and geometric descriptions.
- **Newton and Leibniz:** independent development of calculus and the importance of definitions and notation.
- **Euler and Gauss:** structural generalization, number theory, analysis, and computational insight.
- **Noether:** symmetry and invariants as organizing principles.
- **Turing and Shannon:** computation, information, and formal models.

These are not decorative biographies: each profile must link to a lesson, a primary-source excerpt or reliable source record, a reasoning exercise, and a modern transfer problem.

## Video and external resources

Videos are optional supplements selected by learner interest and pathway. They never replace the core lesson, worked examples, practice, or assessment. Store title, creator, canonical HTTPS URL, rights/license or reuse status, transcript/caption availability, language, and the lesson objective served. Never imply Merlin owns or rehosts third-party media. Prefer resources with captions/transcripts and accessible alternatives.

## Adaptive learner model

Maintain a multidimensional learner state by canonical idea and skill dimension, not one global ability score. Dimensions include recognition, conceptual explanation, procedure, representation translation, algorithm design, proof justification, uncertainty, transfer, and retention.

Recommendation inputs:
- prerequisite readiness;
- evidence count and independence across sessions;
- uncertainty in each skill estimate;
- delayed retrieval and transfer evidence;
- learner pathway weights, interests, pace, and available study time;
- task difficulty and estimated learning value.

Recommendation outputs must include a reason trace and blocked-prerequisite explanation. Preference matching may reorder eligible work but must not alter mastery. A single submission, hint use, AI response, or finite experiment must not certify mastery. Spaced retrieval should be scheduled from demonstrated retention and error patterns, not an arbitrary universal interval.

Current learner estimation is an inspectable Beta(1,1) baseline, not a validated psychometric instrument. Before using it for certification or high-stakes decisions, calibrate item difficulty, compare against expert judgments and held-out cohorts, and assess fairness and uncertainty.

## Assessment, evidence, and formal proof boundaries

- Learner work is append-only and identified by a stable submission ID.
- Assessment and rubric versions are immutable and tied to the exact course version.
- Human review is a separate, auditable record; reviewer feedback is returned to the learner.
- Reviewer rubric scores remain instructional metadata until reviewer qualification, calibration, and evidence-ingestion rules are independently validated.
- Mathematical computation records seed, bounds, precision, solver/version, environment, runtime, and output digest.
- Counterexample search records domain, method, seed, termination, and exact claim it tests.
- Lean receipts bind source digest, toolchain, dependency lock, compiler result, stdout/stderr, and exact artifact identity.
- CACE independently verifies the exact artifact digest and typed provenance.
- No course completion or assessment acceptance is a formal proof. A proof claim is qualified only by the relevant proof and verification pipeline.

## Ranked engineering roadmap

### P0 — Complete the learner submission loop
- Append-only submission storage, idempotency, authenticated learner ownership, active enrollment checks.
- Independent reviewer queue, feedback, and learner-visible review history.
- Regression tests for tenant isolation, identity collision, idempotency, author self-review, and status transitions.
- **Acceptance:** a learner submits an exercise, an independent reviewer reviews it, the learner reads feedback, and no mastery/proof state changes implicitly.

### P1 — Evidence and rubric qualification
- Version assessment rubrics and attach exact assessment/rubric hashes to submissions and reviews.
- Add reviewer qualification records and independent-review policy.
- Define a calibrated mapping from rubric evidence to skill dimensions; preserve uncertainty and session independence.
- Add explicit evidence-ingestion policy; no ingestion before calibration tests pass.
- **Acceptance:** repeated, delayed, transfer evidence changes only the intended skill estimates, with a traceable source and no cross-tenant leakage.

### P2 — Expand the curriculum graph
- Convert the 41-node idea catalog into a staged, prerequisite-validated program map.
- Add discrete mathematics, logic, algebra/functions, geometry, linear algebra, calculus, probability/statistics, numerical methods, and research labs.
- Map each module to all three pathways, with alternate examples and assessments.
- **Acceptance:** every published lesson has validated prerequisites, pathway coverage, objective mapping, task, rubric, transfer prompt, and source provenance.

### P3 — Historical and interest-driven teaching
- Add pioneer profiles, primary-source extracts, and modern reconstruction lessons.
- Add curated, accessible video supplements with rights/provenance metadata.
- **Acceptance:** each external resource is verified, optional, accessible, and linked to a specific learning objective.

### P4 — Retrieval and adaptive scheduling
- Add spaced retrieval queues, learner-controlled cadence, confidence-aware review, and misconception-specific remediation.
- Compare recommendation outcomes on held-out learner/task data.
- **Acceptance:** scheduling improves delayed retention and transfer over a documented baseline without increasing unnecessary repetition.

### P5 — Formal mathematics and computational labs
- Connect selected course claims to Lean 4 proof tasks and pinned compile receipts.
- Add reproducible exact/numerical experiments and finite counterexample search.
- Add independent CACE verification for proof artifacts and provenance.
- **Acceptance:** every result is labeled by evidence strength; no numerical result or model-generated proof is misrepresented as formal verification.

### P6 — Production service qualification
- Complete institution identity/SSO, tenant authorization, rate limits, encrypted storage, retention/deletion controls, backup/restore, observability, accessibility, and incident procedures.
- Execute the complete test suite on a working hosted runner and archive commit-bound artifacts.
- Perform privacy, security, load, recovery, and fairness reviews.
- **Acceptance:** deployment gates pass with reproducible receipts. Until then the LMS remains a development integration, not a production-qualified service.

## Current implementation boundary

Implemented in the current mathematics LMS branch: seven-objective foundations course; a three-objective logic/discrete mathematics course (quantifiers, sets/relations/functions, graphs/trees); a five-objective algebra/functions course (patterns, variables, sets, equations/inequalities, function composition/inverses); three pathway modules per course, with lesson coverage validated; the logic/discrete and algebra/functions courses currently include all lessons in each pathway; tenant-scoped learner profiles; prerequisite-aware recommendations; independent course publication review; optional supplementary video links; append-only exercise submissions; reviewer queue and feedback; learner-visible review history; a 57-idea canonical curriculum map and pathway validator.

Not yet qualified: executable hosted CI for the current branch, production institution SSO and hosted tenancy, reviewer qualification/calibration, validated psychometrics, spaced retrieval scheduler, full curriculum coverage, Lean/CACE course evidence bridge, and production operations controls.
