# Merlin Universal Research Competency Framework (URCF) v1

**Status:** proposed implementation baseline; draft PR  
**Purpose:** train, assess and coordinate Merlin agents to perform reproducible research across scientific, engineering, social-scientific, humanities and creative domains.  
**Implementation:** `python/merlin/research_curriculum.py`

## 1. Executive finding

The strongest human experts are not defined only by the facts they know. They combine deep domain knowledge with repeatable research practices: framing questions, finding primary evidence, reconstructing theories, choosing methods, designing measurements, building instruments and software, analyzing uncertainty, testing alternatives, replicating results, communicating limitations and teaching others.

Merlin should train those abilities as reusable competencies, then attach domain-specific methods, instruments, safety constraints and assessment rubrics. A competence is not a prompt instruction and not a self-reported score. It is an assessed capability backed by artifacts, logs and independent review.

The taxonomy is intentionally overlapping. Mathematics supports physics, economics and computer science; statistics supports medicine and social science; materials science spans chemistry, physics and engineering; cognitive science spans psychology, neuroscience, linguistics and AI. The registry must model many-to-many relationships rather than force disciplines into mutually exclusive boxes.

## 2. What an expert researcher does

Every domain curriculum should cover the following work, with domain-specific variants.

1. **Observe:** identify phenomena, anomalies, patterns, missing measurements and relevant context.
2. **Frame:** turn a broad problem into a bounded question, operational definitions and explicit scope.
3. **Reconstruct:** learn the field's history, foundational concepts, accepted results, open disagreements and known limitations.
4. **Source:** locate primary literature, datasets, standards, archival material, instruments and software; record provenance and versions.
5. **Model:** construct conceptual, mathematical, causal, computational or interpretive models.
6. **Hypothesize:** state competing explanations and predictions that distinguish them.
7. **Design:** select proof, experiment, observation, survey, simulation, fieldwork, archival analysis or engineering test.
8. **Measure:** specify units, calibration, controls, sampling, resolution, uncertainty and data quality.
9. **Implement:** build the apparatus, software, protocol, prototype, formalization or analytical pipeline.
10. **Analyze:** use appropriate mathematics, statistics, computation and domain interpretation.
11. **Challenge:** search for counterexamples, confounders, artifacts, alternative explanations and methodological flaws.
12. **Replicate:** reproduce the result from declared inputs, source versions, code, parameters and procedures.
13. **Synthesize:** connect evidence across studies and disciplines without erasing disagreements.
14. **Communicate:** create notebooks, proofs, datasets, models, technical reports, diagrams and accessible explanations.
15. **Teach:** diagnose misunderstanding, explain methods, assign exercises and assess demonstrated transfer.
16. **Govern:** follow ethics, privacy, biosafety, human-subject, environmental, professional and legal review requirements appropriate to the domain.

A strong agent must know when a task is outside its competence and route it to a specialist or human expert.

## 3. Domain and subdomain coverage

The executable taxonomy in `research_curriculum.py` is the canonical initial list. The following describes the work that must be taught in each family.

### 3.1 Mathematics and formal sciences

**Subdomains:** pure and applied mathematics; algebra; number theory; analysis; geometry; topology; logic; set and category theory; combinatorics; graph theory; probability; statistics; optimization; numerical analysis; differential equations; information theory; computability; formal methods.

**Expert work:** define structures precisely; derive consequences; prove theorems; construct counterexamples; discover invariants; classify objects; estimate bounds; design algorithms; formalize arguments; test conjectures computationally.

**Training:** mathematical language and notation; proof patterns; abstraction; counterexample construction; symbolic and numerical computation; Lean or other proof-assistant workflows; proof dependency and axiom audits; reproducible notebooks. Assess with unseen problems, proof reconstruction, counterexample search, formal checking and independent review. Never treat numerical agreement as proof.

### 3.2 Physics and astronomy

**Subdomains:** mechanics; electromagnetism; optics and photonics; thermodynamics; statistical mechanics; quantum mechanics and information; quantum field theory; particle and nuclear physics; relativity; cosmology; condensed matter; materials physics; plasma; atomic, molecular and optical physics; astrophysics; astronomy; biophysics; geophysics.

**Expert work:** derive equations from physical assumptions; identify symmetries and conservation laws; connect models to observables; design experiments; calibrate sensors; analyze detector and telescope data; run analytical, numerical and Monte Carlo models; compare predictions with measurement.

**Training:** units and dimensional analysis; mechanics and fields; mathematical methods; uncertainty propagation; laboratory and observational methods; simulation validation; model comparison; data provenance; reproducible computational physics. Quantum research additionally needs explicit state preparation, measurement, noise, calibration and hardware-versus-simulator distinctions.

### 3.3 Chemistry and materials

**Subdomains:** organic, inorganic, physical, analytical and computational chemistry; biochemistry; chemical biology; electrochemistry; catalysis; polymers; nanomaterials; crystallography; surface science; semiconductors; battery materials.

**Expert work:** predict and characterize molecular structure; design synthesis routes; measure reaction kinetics and thermodynamics; interpret spectra; model electronic structure; characterize phases and surfaces; assess purity, reproducibility and material performance.

**Training:** chemical notation; stoichiometry; thermodynamics and kinetics; spectroscopy and microscopy; molecular simulation; instrument calibration; laboratory records; uncertainty; chemical safety and waste handling. Wet-lab actions require domain-specific human authorization and institutional controls.

### 3.4 Biology and life sciences

**Subdomains:** molecular and cell biology; genetics, genomics and epigenetics; evolution; ecology; developmental biology; microbiology; virology; immunology; neuroscience; systems and synthetic biology; botany; zoology; marine and computational biology.

**Expert work:** design controls; formulate mechanistic models; select organisms, cell systems or datasets; perform microscopy and sequencing analysis; investigate causal pathways; analyze populations and ecosystems; distinguish correlation, mechanism and evolutionary explanation.

**Training:** molecular foundations; experimental design; controls and replication; omics pipelines; microscopy; statistical power; contamination and batch effects; model-organism limitations; biosafety and ethical review. Human or animal studies require the appropriate review and authorization.

### 3.5 Medicine and health

**Subdomains:** anatomy; physiology; pathology; clinical specialties; surgery; pharmacology; toxicology; epidemiology; biostatistics; public health; psychiatry; rehabilitation; nutrition; imaging; biomedical engineering; health informatics; translational medicine.

**Expert work:** interpret evidence and diagnostics; assess differential explanations; design clinical and population studies; evaluate treatment effects; monitor adverse events; translate findings into clinical research and practice.

**Training:** evidence hierarchies; clinical study design; diagnostic performance; causal inference; biostatistics; trial phases; systematic reviews; privacy; medical-device and clinical governance. The AI role is research support, not independent clinical authority or a substitute for licensed professionals.

### 3.6 Earth, environment and planetary sciences

**Subdomains:** geology; geophysics; geochemistry; meteorology; climatology; oceanography; hydrology; soil and environmental chemistry; paleontology; paleoclimatology; geospatial science; natural hazards; planetary science; astrobiology; conservation.

**Expert work:** collect field observations; interpret spatial and temporal data; reconstruct past conditions; model coupled systems; validate remote-sensing products; quantify uncertainty; compare scenarios and forecast limits.

**Training:** field methods; GIS and remote sensing; geostatistics; geochemical and geophysical methods; climate and fluid models; sensor calibration; data assimilation; uncertainty and scenario analysis.

### 3.7 Computer science and AI

**Subdomains:** algorithms; data structures; complexity; languages and compilers; operating systems; distributed systems; databases; machine learning; deep learning; reinforcement learning; AI agents; multi-agent systems; knowledge representation; vision; robotics; NLP; information retrieval; knowledge graphs; formal verification; software engineering; quantum computing; HCI.

**Expert work:** specify problems; design abstractions and algorithms; implement systems; profile and benchmark; evaluate generalization; verify invariants; debug; perform ablations; document dependencies; reproduce results; assess usability and operational reliability.

**Training:** programming fundamentals; algorithms; architecture; testing; version control; data engineering; model evaluation; experiment tracking; security and privacy; formal methods; deployment and observability. Model capability, reliability and authority must be evaluated separately.

### 3.8 Engineering and applied technology

**Subdomains:** mechanical, electrical, civil, aerospace, automotive, chemical, process, biomedical, biomechanical, robotics, mechatronics, control, structural, geotechnical, manufacturing, industrial, energy, power, semiconductor, systems, reliability, CAD/CAM/CAE.

**Expert work:** translate needs into requirements; develop engineering models; calculate loads, tolerances and margins; create CAD and circuit designs; simulate; prototype; test; inspect; verify; maintain traceability from requirement to result.

**Training:** requirements engineering; dimensional analysis; materials and manufacturing; CAD/CAE; circuit and control simulation; test plans; tolerance analysis; design reviews; configuration management; standards; safety cases and qualified human sign-off.

### 3.9 Social and behavioral sciences

**Subdomains:** psychology; cognitive science; sociology; anthropology; economics and econometrics; political science; international relations; human geography; demography; behavioral science; education; organizational science; communication and media studies.

**Expert work:** formulate operational constructs; design surveys and experiments; sample populations; conduct interviews and ethnography; analyze causal relationships; interpret context; compare theories and measure external validity.

**Training:** research ethics; sampling; survey construction; qualitative coding; statistical inference; causal identification; measurement validity; cultural and contextual interpretation; privacy and reproducibility.

### 3.10 Humanities, language and history

**Subdomains:** history and historiography; philosophy and ethics; linguistics and philology; literature; comparative studies; archaeology; cultural heritage; religious studies; intellectual history; translation; textual criticism; rhetoric and discourse analysis.

**Expert work:** establish source provenance; interpret texts in context; compare translations and manuscripts; reconstruct chronology; evaluate material evidence; distinguish primary evidence from later interpretation; present defensible competing readings.

**Training:** source criticism; archival methods; language and textual analysis; chronology; interpretive frameworks; translation uncertainty; citation; argument reconstruction; respectful treatment of contested evidence.

### 3.11 Economics, business and organizations

**Subdomains:** finance; accounting; actuarial science; operations research; supply chains; management; organizational behavior; entrepreneurship; innovation; marketing; consumer research; decision and game theory.

**Expert work:** model incentives and constraints; quantify uncertainty; design forecasts; evaluate interventions; optimize allocations; analyze markets and organizations; test assumptions against data.

**Training:** accounting and financial mathematics; optimization; econometrics; decision theory; forecasting; scenario analysis; causal inference; model-risk assessment; data provenance and disclosure.

### 3.12 Design, arts and creative research

**Subdomains:** architecture; urban design; industrial and product design; graphic and interaction design; music theory and acoustics; visual arts; computational art; film; animation; digital media; human-centered design; creative technology.

**Expert work:** investigate user needs; develop concepts; make prototypes; evaluate usability and accessibility; analyze form, sound, movement and aesthetics; connect constraints to a finished artifact.

**Training:** design research; visual and spatial reasoning; iterative prototyping; critique; accessibility; material and production constraints; user testing; documentation and portfolio assessment.

### 3.13 Interdisciplinary and emerging research

**Subdomains:** complex systems; network science; systems neuroscience; computational social science; bioinformatics; computational medicine; climate economics; sustainability; origins of life; science of science; automated laboratories; AI-assisted discovery.

**Expert work:** translate methods between fields; identify shared structures; integrate heterogeneous evidence; expose incompatible assumptions; build multi-scale models; coordinate specialist teams.

**Training:** ontology alignment; dimensional and semantic checks; interdisciplinary literature maps; systems modeling; uncertainty propagation across interfaces; cross-domain benchmark tasks; expert adjudication.

## 4. A common inductive training sequence for every subdomain

Each specialty is trained from concrete work toward independent research. The sequence is the same; content, instruments, risk controls and rubrics vary by domain.

| Stage | Human-expert behavior to reproduce | AI training and assessment |
|---|---|---|
| 0. Orientation | Explain what the field studies and why | Concept map, vocabulary, scope and boundaries |
| 1. Foundations | Use core concepts and notation | Retrieval practice, derivations, worked examples |
| 2. Methods | Choose and operate standard methods | Method selection cases, instrument/software exercises |
| 3. Guided practice | Solve known problems with supervision | Stepwise tasks with feedback and error diagnosis |
| 4. Critical practice | Compare explanations and find flaws | Blind review, counterexamples, confounder search |
| 5. Reproduction | Recreate an established result | Exact source, version, data and environment replay |
| 6. Independent project | Complete a bounded new investigation | Approved task, budget, artifacts, logs and report |
| 7. External examination | Defend choices before a specialist | Blind rubric, adversarial questions, independent rerun |
| 8. Continuing education | Update methods as the field changes | Drift monitoring, literature refresh and requalification |

No stage is passed merely because an agent generated a plausible answer. Advancement requires an assessment record and the evidence specified by the unit.

## 5. The Hermes teaching organization

Hermes should coordinate a small teaching faculty of specialized agents. The teacher roles should be separate from the agents whose work they assess.

### 5.1 Hermes — chief teacher and curriculum coordinator

Responsibilities:
- Maintain each agent's competency profile and training history.
- Diagnose task failures and convert them into learning objectives.
- Select the next prerequisite or remedial lesson.
- Assign domain specialists and collect their assessments.
- Schedule spaced retrieval and cumulative assessments.
- Dispatch practice tasks using Merlin's engineered-prompt contract.
- Require structured results, evidence and explicit limitations.
- Escalate ambiguous, high-impact or regulated work to human experts.

Hermes should not certify its own expertise or waive the external-review requirement.

### 5.2 Coder-Teacher — dedicated software engineering instructor

This is a distinct role, not simply a coding persona embedded in Hermes.

It teaches Hermes and every other AI subsystem to:
1. Read repository structure and identify the actual source of truth.
2. Trace a request through API, event, worker, persistence and UI boundaries.
3. Understand types, interfaces, contracts and dependency graphs.
4. Write minimal, reviewable patches.
5. Add unit, integration, regression and property-based tests.
6. Reproduce defects and preserve failing logs before changing code.
7. Diagnose CI failures from exact logs, not assumptions.
8. Use Git branches, commits and pull requests correctly.
9. Verify the exact commit tested and retain artifacts.
10. Review security, privacy, licensing and operational implications.
11. Write migration, rollback and deployment procedures.
12. Explain code changes and teach the receiving agent to maintain them.

**Coder-Teacher practical examinations:**
- Fix a deliberately seeded bug without unrelated changes.
- Write a regression test that fails before the patch and passes after it.
- Reproduce an existing CI run from its recorded commit.
- Identify a stale or incorrect interface contract.
- Implement an API adapter with typed inputs, bounded outputs and explicit errors.
- Demonstrate that a failed test cannot be silently reported as success.
- Teach Hermes to perform the same task on a separate repository.

The teacher should assess code quality, test quality, reproducibility and explanation—not just whether generated code compiles.

### 5.3 Other teacher roles

| Teacher | Teaches | Examination |
|---|---|---|
| Mathematics teacher | Derivation, abstraction, proof and counterexamples | Unseen problems and formal proof |
| Experimental-methods teacher | Hypothesis, measurement and controls | Design and critique an experiment |
| Computational-science teacher | Numerical models and simulation | Independent reproduction and validation |
| Evidence teacher | Sources, provenance and uncertainty | Blind evidence audit |
| Engineering teacher | CAD, circuits, systems and design verification | Build, simulate and test an artifact |
| Scientific-writing teacher | Papers, technical reports and synthesis | Source-traceable report and oral defense |
| Ethics and governance teacher | Domain-specific research obligations | Scenario-based review and escalation |

A teacher may provide instruction and formative feedback. A separate assessor or external reviewer should decide whether the competency has been demonstrated.

## 6. Agent-specific training profiles

Every agent receives the shared foundation, followed by a role-specific curriculum.

| Agent/subsystem | Core training | Required outputs |
|---|---|---|
| Hermes | Teaching, orchestration, research planning and evaluation | Curriculum plans, dispatch records, assessments |
| Coder-Teacher | Software engineering and verification pedagogy | Patches, tests, CI logs, code lessons |
| Expert Robot | Repository research, coding and bounded execution | Reproducible worker results |
| CACE | Provenance, artifact verification and formal evidence boundaries | Verification receipts and audit trails |
| MCFC | Resource allocation, constraints, leases and scheduling | Budget and lease decisions |
| Avrea workers | Environment setup, computation, testing and reporting | Runner identity, tool versions and artifacts |
| Lean/formal agents | Definitions, theorem proving, proof dependencies and counterexamples | Checked proof artifacts |
| CAD/engineering agents | Requirements, geometry, constraints, simulation and design review | Native CAD, engineering IR and test evidence |
| Research agents | Literature, theory, experiment and synthesis | Research dossiers and reproducible results |
| Dashboard/observability agents | Metrics, event lifecycle and evidence display | Read-only status views and audit records |

No agent inherits permissions simply because it passes a curriculum assessment. Competence and authority remain independent.

## 7. Assessment and competency evidence

Use five levels:

- **Orientation:** can explain the purpose, vocabulary and boundaries.
- **Foundation:** can solve standard guided tasks.
- **Practitioner:** can perform routine tasks with review.
- **Independent:** can complete bounded tasks and reproduce results.
- **Expert:** can handle novel cases, critique methods and defend conclusions under independent examination.

Every pass record must contain:
- agent and competency identifiers;
- curriculum unit and version;
- assessor identity and timestamp;
- assessment status and rubric;
- source and tool versions;
- evidence references and artifact hashes;
- test logs and failures;
- limitations and unresolved gaps;
- independent replication and external review for independent/expert levels.

A self-rating, benchmark score or language-model confidence estimate is not a competency pass. Training records must be append-only or versioned so that later corrections do not erase earlier assessment history.

## 8. Use the Merlin components that already exist

Do not wait for the whole Merlin platform to be complete. The following pieces can be used now, subject to their stated boundaries.

| Existing component | Immediate use in the research school | What it does not establish |
|---|---|---|
| `prompt_contract.py` | Compile lessons, examinations and research tasks into deterministic prompts | A live Hermes consumer |
| `PromptOutboxPublisher` | Publish idempotent task events to registered recipients | Remote delivery by itself |
| `PromptResultReceiver` | Validate worker identity, lease and result correlation | A live authenticated remote endpoint |
| `PromptCaceEvidenceBridge` | Submit declared artifact hashes and metadata to the CACE adapter | Scientific validity or theorem proof |
| `event_outbox.py` | Durable task lifecycle, leases and acknowledgements | Complete distributed event transport |
| `research_dispatch.py` | Rank and dispatch approved research candidates | Automatic authorization |
| `hypothesis_ledger.py` | Store research hypotheses and their lifecycle | Independent confirmation of claims |
| `research_optimizer.py` | Advisory prioritization of research candidates | Authority to override review gates |
| `project_registry.py` | Canonical project/artifact storage and hash verification | Proof that artifact content is true |
| `cace_adapter.py` | Independent artifact verification boundary | Mathematical proof unless a formal proof checker supplies it |
| Lean/formal workflows | Verify formalized mathematical claims | Truth of assumptions or applicability to physical systems |
| Avrea CI | Run reproducible tests and preserve logs | Production qualification of every subsystem |

The immediate goal is to connect these components into a working teaching and research cycle. Do not replace functioning components with a second orchestration engine.

## 9. The research lesson/task/result lifecycle

1. Hermes selects a competency gap or research objective.
2. The curriculum registry resolves prerequisites and a versioned unit.
3. Hermes compiles a `PromptTask` for the teacher or student agent.
4. The publisher records the task in the durable outbox.
5. A registered worker claims the event with a lease.
6. The worker returns a `PromptResult` with tests, tool versions, limitations and artifact hashes.
7. The result receiver validates task identity and acknowledges the event.
8. The artifact registry stores canonical outputs.
9. CACE independently checks artifact bytes and provenance where configured.
10. A separate assessor scores the work and writes a competency record.
11. Hermes updates the next training objective, not the agent's authority.
12. The research dashboard displays progress, failures, evidence and review status.

All attempted pull requests and CI runs must retain actual test logs and machine-readable results, including failed and skipped tests. A missing log is an evidence gap, not a pass.

## 10. Production implementation plan, ranked

### P0 — Make the curriculum executable
- Add the versioned domain and competency registry.
- Add unit validation and training-plan generation.
- Add assessment-record validation.
- Add Hermes and Coder-Teacher profiles.
- Test malformed units, missing evidence, invalid levels and attempted self-certification.

### P1 — Integrate Hermes teaching dispatch
- Add a curriculum query interface.
- Convert a curriculum unit into a typed `PromptTask`.
- Publish through the existing outbox.
- Register teacher and student recipients explicitly.
- Require a result envelope and durable acknowledgement.
- Add a real Hermes consumer and authenticated result transport; do not call the loop complete until a live round trip is observed.

### P2 — Build the coder-teacher practicum
- Create a repository-reading lesson.
- Create a failing-test-first debugging lesson.
- Create patch, regression-test and CI-evidence lessons.
- Use Expert Robot and Avrea for isolated practical tasks.
- Have Hermes complete the same exercises under Coder-Teacher assessment.
- Keep code review and merge authority separate.

### P3 — Evidence and competency ledger
- Store unit versions, assessments, artifacts and assessor identities.
- Bind evidence to exact commit, source and tool versions.
- Use CACE to verify artifact bytes and provenance.
- Add formal proof references when Lean is the verifier.
- Keep scientific claims, artifact integrity and formal validity as separate statuses.

### P4 — Domain laboratories
Start with a small number of real, bounded pilot domains:
1. Mathematics and Lean proof research.
2. Physics and computational simulation.
3. Software engineering and AI evaluation.
4. CAD, electronics and ngspice engineering.
5. Biology/biomedical literature and public-data research.
6. Climate and earth-science data analysis.

Each pilot should produce a reproducible result before expanding the number of specialties.

### P5 — Research dashboard
Show:
- competency coverage by agent and domain;
- current learning stage;
- tasks assigned, leased, completed and blocked;
- CI run and test-log status;
- evidence completeness;
- CACE verification status;
- formal proof status;
- human review status;
- compute budget and research priority;
- unresolved questions and next action.

### P6 — Continuous curriculum improvement
- Mine failure logs for recurring skill gaps.
- Convert recurring errors into new lessons and regression tests.
- Use blind exams to measure actual transfer.
- Refresh curricula when methods or standards change.
- Compare independent agents on identical tasks.
- Retire weak lessons and retain their version history.

## 11. Production rules

1. Capability grows; authority never expands automatically.
2. A prompt is a task description, not a permission grant.
3. A passing test is evidence about that test, not a universal correctness claim.
4. A CACE artifact receipt is not a mathematical proof.
5. A Lean proof is conditional on its assumptions and dependencies.
6. A simulation is not an observation of nature.
7. A literature summary is not independent replication.
8. A teacher cannot certify its own student without an independent assessment path.
9. A failed or skipped test must remain visible.
10. Human review is mandatory wherever domain policy, professional judgment, safety or law requires it.

## 12. First acceptance milestone

Merlin should not claim to have a universal research school until it can demonstrate this one complete path:

- Hermes identifies a real competency gap.
- Hermes assigns a versioned curriculum unit.
- Coder-Teacher teaches a concrete coding/research method.
- Expert Robot performs a bounded practical exercise.
- Avrea runs the exact test suite and preserves logs.
- The worker returns a hash-bound result.
- The artifact is registered and independently checked by CACE.
- A separate assessor scores the result.
- Hermes records the evidence and selects the next lesson.
- The dashboard shows the complete lifecycle, including failures.

This milestone is deliberately smaller than the full ambition. Once it works, the same machinery can be instantiated across the entire domain taxonomy without inventing a separate training architecture for every specialty.
