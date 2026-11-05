# Merlin Learning — University LMS Product Blueprint v0.1

**Status:** product/architecture proposal; not a production implementation  
**Parent platform:** Merlin / Expert Robot research and curriculum infrastructure  
**Commercial model:** institution-licensed SaaS or institution-hosted deployment, with course, faculty, department and campus tiers

## 1. Product thesis

Merlin Learning is an adaptive university learning environment that combines:
- evidence-informed personalized instruction and practice;
- mastery-oriented spaced repetition and retrieval;
- intellectual and social history of each subject;
- globally sourced media, primary sources, simulations and creative activities;
- instructor-authored courses with AI-assisted course preparation;
- institutional administration, assessment, analytics, accessibility and interoperability.

The product should make sustained study intrinsically rewarding through curiosity, agency, visible competence, meaningful challenge, social learning and useful feedback. Do not optimize for compulsive engagement, streak anxiety, dark patterns or time-on-platform. Optimize for durable learning, transfer, student wellbeing and course completion.

## 2. Learning model

Every course is represented as a versioned graph:
- Course -> modules -> learning objectives -> concepts/skills -> prerequisite relations.
- Each objective links to explanations, historical context, examples, media, practice items, assessments and evidence.
- Each item has provenance, rights/license, accessibility metadata, discipline, level, language, cultural context and review status.

A learner model stores per-objective estimates, not a single opaque student score:
- current mastery estimate and uncertainty;
- last successful and failed retrieval;
- response latency where appropriate;
- error/misconception categories;
- confidence calibration;
- transfer performance across contexts;
- preferred/accessible presentation modes;
- next review window and reason.

Adaptation chooses the next useful activity based on prerequisite gaps, objective importance, estimated forgetting, uncertainty, workload and course schedule. Students and instructors can inspect why a recommendation was made and override it.

### Instruction and practice repertoire

Use these as selectable strategies, not one-size-fits-all rules:
1. Retrieval practice: free recall, short answer, explain-from-memory, diagram reconstruction and low-stakes quizzes.
2. Spaced practice: schedule reviews using performance and desired retention horizon; support short, medium and cumulative review.
3. Interleaving: mix related problem types after initial orientation so students learn to discriminate methods.
4. Elaboration: ask why/how, causal explanation, comparison, analogy and connection to prior knowledge.
5. Worked examples and fading: show expert reasoning, then progressively remove scaffolding.
6. Dual coding and multimodal explanation: coordinated text, diagrams, audio, animation and tactile/interactive representations.
7. Self-explanation and metacognition: confidence, error analysis, reflection and study planning.
8. Transfer and application: novel contexts, projects, simulations, case studies and interdisciplinary problems.
9. Collaborative learning: peer explanation, structured discussion, group problem solving and instructor feedback.
10. Mastery reassessment: revisit objectives using new item variants, not repeated memorization of identical questions.

The platform must respect domain differences: language fluency, mathematical proof, laboratory technique, clinical reasoning, historical interpretation and studio practice need different evidence and practice formats.

## 3. Intellectual-history layer

Every major topic should offer a structured historical pathway:
- the question/problem before the breakthrough;
- historical setting, institutions, tools, constraints and available knowledge;
- biographies and intellectual networks of contributors;
- original documents, notebooks, letters, diagrams, instruments, publications and artifacts where rights permit;
- competing explanations, disputes, failed hypotheses and abandoned approaches;
- contributions across cultures, regions, languages and traditions;
- how later evidence revised the original account;
- present-day applications and open questions.

Do not flatten history into a lone-genius story. Distinguish primary sources, later scholarship, contested claims and narrative reconstruction. Show dates and uncertainty. Include women, non-European traditions, collaborative teams and historically marginalized contributors where supported by reliable sources.

### Historical lesson template

1. Start with a puzzle or authentic problem.
2. Give the learner the information/tools available at that historical moment.
3. Ask what they would try and why.
4. Reveal the historical approaches and competing hypotheses.
5. Compare the learner's reasoning with documented historical reasoning.
6. Show the evidence that changed the field.
7. Revisit the modern concept and solve a new problem.

## 4. Global media and content

Support licensed and openly licensed material from around the world:
- public-domain books, archives, maps, manuscripts and scientific instruments;
- open educational resources and university collections;
- museum and library media;
- documentaries, lectures, interviews, podcasts and music where rights permit;
- interactive maps, timelines, 2D/3D models, simulations, datasets and virtual labs;
- student-created explanations and faculty-curated collections.

Every media object needs source attribution, license/rights status, creator, language, region, date, transcript/captions or equivalent accessibility, and review metadata. Never scrape or redistribute copyrighted media without permission. Link or embed under the source's terms. Offer translated captions, transcripts, glossaries and culturally contextualized explanations.

AI-generated teaching media must be labeled as generated and must not be presented as historical primary evidence.

## 5. Personalized student experience

- Initial diagnostic that is low-stakes and revisable.
- Student-selected goals, pace, study availability and preferred modalities.
- Daily/weekly study queue sized to realistic workload.
- Course map showing mastered, developing and not-yet-learned objectives.
- Review calendar with transparent reasons for due items.
- Multiple explanation paths: concise, detailed, visual, historical, example-first, formal, audio and multilingual.
- Tutor dialogue that asks students to reason before revealing answers.
- Accessibility preferences and accommodations that do not reduce academic expectations.
- Offline/low-bandwidth options and mobile-first interaction.
- Student controls to inspect, correct and export their learning record.

## 6. Instructor and department experience

Faculty author or import a course, map objectives, select content, set assessment policy and approve AI-generated materials. The AI may draft explanations, question variants, historical pathways and feedback, but instructors retain control over course outcomes and grading policy.

Instructor tools:
- syllabus and course import;
- objective/prerequisite mapping;
- content and question authoring;
- rubric and assessment design;
- review of generated material with source citations;
- misconception and cohort-level reports;
- intervention queues based on transparent signals;
- accommodations and alternative formats;
- gradebook export and LMS launch integration;
- version history and audit trail.

Department and institution tools:
- multi-course and multi-department administration;
- roles and scoped permissions;
- institution-level identity integration;
- retention/deletion/export policies;
- aggregate analytics with minimum cohort thresholds;
- course quality and accessibility review;
- procurement, licensing and usage reporting;
- institution-managed content and data residency options where feasible.

## 7. Roles and agent architecture

Use Merlin's existing research-school curriculum as the competency foundation. Add distinct learning agents with bounded roles:

- **Hermes Learning Coordinator:** selects next lesson/review, resolves prerequisites, coordinates agents and explains recommendations.
- **Subject Teacher:** teaches discipline-specific concepts and adapts explanations.
- **Learning Scientist:** selects instructional strategy and evaluates whether it is appropriate for the objective.
- **History-of-Ideas Teacher:** constructs source-grounded intellectual-history pathways.
- **Media Curator:** finds, checks rights/provenance, tags and contextualizes media.
- **Assessment Designer:** creates parallel items, rubrics and transfer tasks.
- **Feedback Coach:** diagnoses misconceptions and gives scaffolded feedback without simply giving away answers.
- **Accessibility/Linguistic Reviewer:** checks readability, captions, translations and alternate formats.
- **Faculty Copilot:** assists instructors but never silently changes official course policy or grades.
- **Independent Assessor:** evaluates mastery independently of the teaching agent.

The Coder-Teacher trains and maintains the software agents and course tooling. Agent competence is versioned and evidenced. Teaching agents cannot self-certify mastery or change their own permissions.

## 8. Architecture and Merlin integration

Build this as a product bounded by stable service contracts, not a separate duplicate AI platform.

Reuse after verifying actual interfaces:
- research curriculum and role-based training plans;
- PromptTask contract and engineered prompt/result envelope;
- Hermes dispatch and event outbox/acknowledgement lifecycle;
- project/artifact registry and provenance;
- CACE evidence bridge for artifact integrity and policy checks;
- Avrea bounded execution for content pipelines, media processing and tests;
- formal verification where useful for scheduling, grading invariants and protocol properties.

Proposed service boundaries:
- Identity/Tenant Service
- Course and Curriculum Service
- Content/Media Provenance Service
- Learner Model Service
- Review Scheduler
- Assessment and Rubric Service
- Tutor/Agent Orchestrator
- Instructor Analytics Service
- Interoperability Gateway
- Audit, Consent and Data Governance Service

Core records: Tenant, User, Role, Course, CourseVersion, Objective, Concept, Prerequisite, LearningResource, MediaAsset, SourceCitation, License, Activity, AssessmentItem, Attempt, LearnerState, ReviewEvent, MasteryEvidence, Intervention, Accommodation, AgentRun, AuditEvent.

Every generated content item and assessment variant records model/agent version, prompt/task version, source references, generation time, reviewer/approval state and content hash. Keep learning events append-only where practical; provide correction and deletion workflows for personal data.

## 9. Interoperability and institutional requirements

Design for integration rather than forcing colleges to replace their existing LMS:
- LTI 1.3 / LTI Advantage for secure launches and tool integration;
- QTI for portable assessment items and tests;
- Caliper Analytics for learning activity events;
- CASE for competency frameworks and standards;
- Edu-API where institutional SIS/academic data exchange is required;
- SSO using institution-supported identity protocols;
- documented REST APIs, webhooks and CSV export/import.

Treat FERPA, applicable state privacy laws, institutional contracts, accessibility obligations and records-retention requirements as product requirements requiring qualified legal and security review. Minimize collected data. Do not sell student data or use identifiable student records to train general models. Provide clear consent, access, correction, export and deletion policies consistent with institutional obligations.

Target WCAG 2.2 AA as a design and testing objective. Include keyboard access, screen-reader semantics, captions/transcripts, color-independent meaning, reduced motion, adjustable text, accessible math and alternative input methods.

## 10. Commercial packaging

Potential packages:
- **Course Pilot:** one course, limited cohort, faculty authoring and learning analytics.
- **Department:** multiple courses, shared content library, departmental reporting and support.
- **Campus:** SSO, institution integrations, governance, custom retention, analytics and campus-wide content.
- **Research Partner:** opt-in, ethics-reviewed learning research using de-identified or appropriately consented data.

Pricing should be validated with actual college buyers. Evaluate per-active-student, per-course and annual institution licensing; avoid assuming willingness to pay before pilot interviews.

## 11. MVP sequence

### Phase 0 — discovery and validation
Interview students, faculty, instructional designers, disability/accessibility staff, IT/security, registrars and procurement. Select one pilot course with measurable learning outcomes and faculty sponsorship. Define baseline and comparison methodology.

### Phase 1 — single-course learning engine
Build course/objective graph, learner state, review queue, retrieval practice, instructor dashboard and a source-grounded history module. Begin with one discipline and a small set of content types.

### Phase 2 — teaching agents and content studio
Add Hermes coordinator, subject teacher, history teacher, media curator, assessment designer and independent assessor. Require faculty approval for published course content and graded assessments.

### Phase 3 — college integration
Add LTI 1.3, QTI import/export, SSO, role-based access, audit logs, data governance, accessibility testing and institutional reporting.

### Phase 4 — pilot evidence
Run a faculty-led pilot with pre-registered outcomes where feasible. Measure delayed retention, transfer, objective mastery, course completion, student workload, accessibility, faculty time and subgroup differences. Compare against a suitable baseline; do not infer efficacy from engagement or satisfaction alone.

### Phase 5 — commercialization
Package tenant isolation, deployment options, service-level commitments, support, procurement documentation, security review, data-processing terms, onboarding and institution-specific configuration.

## 12. Evaluation metrics

Learning outcomes:
- delayed retention at meaningful intervals;
- transfer to novel tasks;
- mastery by course objective;
- misconception resolution;
- confidence calibration;
- course completion and progression.

Experience and equity:
- perceived relevance, curiosity and autonomy;
- sustainable study habits and workload;
- accessibility task completion;
- outcomes across student groups, with privacy-preserving reporting;
- opt-out and disengagement patterns.

Institutional value:
- faculty preparation time;
- time to identify and support struggling students;
- content reuse and accessibility coverage;
- integration reliability;
- adoption and renewal.

Guardrails:
- time-on-platform is not a success metric by itself;
- streaks are optional and never punitive;
- no opaque high-stakes automated grading;
- no unreviewed AI-generated historical claims or citations;
- no hidden profiling or sale of student data;
- instructors and students can understand and challenge consequential recommendations.

## 13. First acceptance milestone

A pilot student enrolls through an institution course launch, completes a diagnostic, receives an adaptive lesson with historically contextualized and properly attributed media, practices a concept through retrieval and worked examples, receives a performance-based review schedule, completes a novel transfer task, and sees a transparent mastery record. The instructor can inspect the objective mapping, sources, assessment rubric and cohort-level results. The institution can audit identity, permissions, data flows and activity records.

All major actions produce reproducible logs and test evidence. A successful demo is not evidence of educational efficacy; that requires a properly designed pilot.
