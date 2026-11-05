# Merlin Math Kung Fu: First-Principles Mathematical Learning Engine v0.1

**Program ID:** MERLIN-MATH-KF-001  
**Status:** learning-engine specification; not yet a deployed interactive product  
**Canonical knowledge:** `docs/research/merlin-mathematical-idea-catalog.v1.json` and `MERLIN_MATHEMATICAL_IDEA_LEDGER_V0.1.md`  
**Learning integration:** Merlin Learning University LMS blueprint and Universal Research Competency Framework

## 1. Purpose

Math Kung Fu is the learner-facing way to explore the mathematics Merlin researches. It should make a learner capable of rebuilding ideas from first principles, understanding why they arose, moving between representations, testing conjectures, and eventually contributing to research.

It is not a second mathematics database or a fixed textbook sequence. Lessons, exercises, simulations and research projects reference canonical mathematical idea IDs, theorem IDs, source records, model versions and evidence receipts.

## 2. Learning principles

1. **First principles before memorized procedures.** Start with the problem an idea solves, construct the objects and operations, then derive methods.
2. **Intellectual history is part of the mathematics.** Explain the historical problem, notation, tools, debates, contributors, alternative approaches and later revisions. Distinguish primary sources from modern reconstructions.
3. **Representations are the central learning instrument.** Move between concrete objects, diagrams, tables, graphs, symbolic expressions, geometric constructions, code and formal proofs.
4. **Visual and interactive exploration.** Use manipulable diagrams, coordinate planes, geometric constructions, sliders, graph plots, vector fields and small simulations when they add explanatory value.
5. **Short explanations, substantial exploration.** Keep narration and on-screen labels concise. Give one new conceptual move at a time; let the learner experiment before expanding.
6. **Adaptive mastery.** Track demonstrated understanding, uncertainty, error patterns, retrieval history and transfer—not just completion or speed.
7. **Research literacy.** Teach the difference between a conjecture, a finite experiment, a proof, an empirical result and an open problem.
8. **No difficulty-first design.** Mathematical depth is the goal; difficulty is adjusted to support understanding, not used as a ranking system.

## 3. The learning object model

Every lesson unit references:
- stable lesson and objective IDs;
- one or more canonical mathematical idea IDs;
- prerequisites as a dependency graph, not merely a grade number;
- motivating question and historical context;
- definitions and constructed examples;
- one primary representation and optional linked representations;
- interactive exploration specification;
- concise explanation and worked example;
- misconceptions and diagnostic prompts;
- retrieval prompts and transfer task;
- assessment rubric and mastery threshold;
- references and provenance;
- accessibility alternatives;
- proof, experiment or simulation evidence when relevant.

Every learner attempt records objective ID, prompt/version, response, correctness rationale, misconception tag, confidence, support level, timestamp and next-review policy. Do not store more personal information than needed for learning.

## 4. A non-linear mathematical dependency map

The course map is a directed graph. A learner may enter through geometry, patterns, games, music, physics, engineering or computation, then follow prerequisite edges as needed.

### Foundation and number sense
- quantity, comparison, counting and units;
- arithmetic as operations on quantities;
- addition, subtraction, multiplication and division as distinct structures;
- fractions, ratios, rates, percentages and proportional reasoning;
- negative numbers, powers, roots and scientific notation;
- estimation, error and dimensional reasoning.

### Patterns and symbolic structure
- sequences, recurrence and invariants;
- variables as names for changing or unknown quantities;
- equality as a relation, not an instruction to calculate;
- expressions, equations, inequalities and functions;
- factoring, substitution and systems of equations;
- proof of algebraic identities.

### Geometry and spatial reasoning
- points, lines, angles, distance and constructions;
- congruence, similarity, area, volume and scaling;
- coordinate geometry and transformations;
- vectors, dot/cross products and matrices;
- Euclidean, spherical and hyperbolic geometry;
- manifolds, charts, curvature and connections.

### Change, accumulation and calculus
- motion, rate and local change;
- limits and continuity;
- derivative as local linear behavior;
- integral as accumulation and measure;
- fundamental theorem of calculus;
- differential equations and dynamical systems;
- multivariable calculus, vector calculus and differential geometry.

### Discrete, probabilistic and computational mathematics
- logic, sets, relations and functions;
- counting, combinatorics and graph theory;
- probability, conditional probability and Bayes' rule;
- statistics, estimation and uncertainty;
- algorithms, complexity and discrete optimization;
- numerical methods and reproducible computation.

### Deeper structures
- linear algebra and spectral theory;
- abstract algebra, groups, rings, fields and modules;
- complex numbers, quaternions and Clifford/geometric algebra;
- topology, category theory and type theory;
- real, complex and functional analysis;
- measure theory, information theory and mathematical physics.

### Research frontiers
- representation-first mathematics and simultaneous frames;
- Xenomaths and glyph-native formal systems;
- n-ary and multi-valued logics, modal/temporal systems and logic composition;
- time crystals, spacetime projections and dynamical structure;
- QFT/UFT mathematical foundations and model qualification;
- n-ality, invariants, algebraic structures and dimensional analysis;
- mathematical morphology, fractals and lacunarity;
- ideonomy, conjecture generation and counterexample search;
- CAD/MCFC/engineering mathematics and physical simulation.

These are research pathways, not assertions that all candidate topics are solved or that all named theories are equally established.

## 5. A standard lesson arc

Each concept is taught through a repeatable but adaptable arc:

1. **Puzzle:** present a concrete question or surprising phenomenon.
2. **Explore:** allow a small interactive experiment before naming the formal concept.
3. **Build:** construct the objects, operations and definitions.
4. **Explain:** give a concise verbal explanation and one worked example.
5. **Represent:** show the same object in another representation and explain what changes or stays invariant.
6. **Derive:** let the learner reconstruct the rule or theorem.
7. **Check:** provide a short recall question or diagnostic prompt.
8. **Transfer:** apply the idea in a new setting such as physics, biology, music, finance, language or engineering.
9. **Reflect:** distinguish what was proved, observed, assumed or left open.
10. **Revisit:** schedule retrieval practice according to demonstrated retention.

The next quiz should normally follow the lesson rather than being interleaved before the explanation unless the learner explicitly chooses a diagnostic challenge.

## 6. Interaction primitives

The client should support typed reusable interactions:
- number line and quantity manipulator;
- fraction/ratio model;
- algebra balance and expression rewrite;
- function input/output explorer;
- coordinate plane and geometric construction;
- transformation and frame comparison;
- vector and matrix explorer;
- graph and parameter slider;
- derivative/tangent and integral/area explorer;
- probability experiment with declared random seed;
- proof-step and counterexample explorer;
- XMG glyph expression builder;
- simulation and phase-space explorer.

Every interactive object must declare the mathematical semantics behind its rendering. A diagram is not a proof; numerical plots are not exact identities; finite random experiments do not establish universal probability theorems. Provide a symbolic or textual alternative for every essential interaction.

## 7. Assessment and adaptation

Mastery is multidimensional:
- conceptual explanation;
- correct use of definitions;
- procedure and calculation;
- representation translation;
- proof/reasoning;
- counterexample recognition;
- estimation and error awareness;
- transfer to an unfamiliar context;
- confidence calibration and delayed retention.

A learner who gives a wrong answer should receive a diagnosis of the underlying misconception, a smaller example or alternate representation, and a chance to retry. Do not merely reveal the correct answer. Revisit earlier errors after increasing intervals and interleave related concepts when readiness is demonstrated.

The system should distinguish:
- not yet introduced;
- attempted but uncertain;
- emerging;
- practiced;
- retained;
- transferable;
- independently explainable;
- research-ready.

These are objective-level learning states, not labels of intelligence or worth.

## 8. History and mathematical culture

For each historical unit, record:
- specific person, school, community or scholarly network;
- location, language and time period;
- original problem and historical conditions;
- source texts and their editions/translations;
- competing approaches and disagreements;
- tools, notation and institutional context;
- later reinterpretations and corrections;
- underrepresented contributors where reliable sources support inclusion.

Do not portray mathematics as a single uninterrupted path toward modern notation. Do not attribute one way of reasoning to an entire culture. Compare specific sources and practices. Separate historical actors' own concepts from modern formal translations.

## 9. Shared system architecture

- **Math Idea Catalog:** canonical IDs, scoped claims, definitions, assumptions, objections and next steps.
- **Equation Atlas:** applied equations, dimensional checks, symbolic/numerical models and reproducibility receipts.
- **XMG:** typed glyph ASTs, symbolic operators, rewrite rules and visual rendering.
- **Lean:** machine-checked theorems and axiom reports.
- **Avrea:** bounded reproducible tests, simulations and build jobs.
- **CACE:** independent artifact/proof receipt verification and provenance checks.
- **Hermes:** learning coordinator and routing to specialist teachers.
- **Coder-Teacher:** lesson tooling, interaction components, parsers, tests and content pipelines.
- **Math/History/Physics/Engineering Teachers:** domain-specific explanation and research supervision.
- **Merlin Learning:** student state, lesson delivery, assessment, spaced review and course authoring.

The same stable idea ID should connect a lesson to its source, model, proof, experiment, code and evidence receipt. No subsystem may silently rewrite a canonical theorem or upgrade a research claim's status.

## 10. Initial pilot lessons

Build these as complete lesson cycles before scaling the catalog:

1. **Division is not just subtraction:** partitioning, measurement, inverse multiplication, fractions and units.
2. **Why negative numbers work:** directed quantities, additive inverses, number line, algebraic consistency and historical notation.
3. **What a function really is:** input-output rules, tables, graphs, mappings and transformations.
4. **One rotation, many representations:** coordinate matrices, complex plane, quaternions and geometric-algebra rotors; explicitly show the assumptions and where each representation applies.
5. **The derivative as local linearity:** secant-to-tangent exploration, rates, units and approximation error.
6. **What a proof establishes:** definitions, assumptions, inference, counterexamples and the difference between finite testing and universal proof.

Each pilot includes a lesson, interactive object, short recall checks, separate transfer quiz, teacher notes, accessibility alternative and source/evidence metadata.

## 11. Acceptance criteria

- Every lesson references canonical mathematical idea IDs.
- Prerequisites form a validated directed graph with cycle detection.
- Every mathematical statement is tagged as definition, conjecture, theorem, empirical claim, model assumption or open question.
- Interactive diagrams have typed semantics and accessible nonvisual alternatives.
- Historical claims cite traceable sources and distinguish primary evidence from modern interpretation.
- Assessment checks reasoning and transfer, not only answer matching.
- Learner state is explainable and correctable.
- Spaced retrieval is based on observed performance and uncertainty.
- Content revisions are versioned and reproducible.
- Formal proof claims link to exact Lean source, toolchain and axiom report.
- Simulation claims link to exact inputs, model, solver, environment and output hashes.
- The learning engine cannot promote mathematical claims or grant execution authority.

## 12. Build sequence

1. Map the existing catalog's mathematical IDs to learning objectives and prerequisite edges.
2. Implement the lesson-unit schema and validator.
3. Build one accessible coordinate/graph interaction and one algebra interaction.
4. Deliver the first three pilot lessons with retrieval and separate transfer assessment.
5. Connect Hermes to learner-state and lesson selection APIs.
6. Add source-backed historical modules and reviewed media.
7. Connect proof/simulation receipts to lessons.
8. Run a small opt-in pilot; measure delayed retention, transfer, misconception recovery and accessibility.
9. Expand only after independent review of learning outcomes.

**Design invariant:** teach the learner to think mathematically, not merely to imitate a procedure. Use the same canonical mathematical objects across research, proof, engineering and education.
