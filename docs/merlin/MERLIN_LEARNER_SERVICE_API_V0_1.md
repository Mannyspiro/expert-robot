# Merlin Learning learner service API v0.1

**Implementation status:** local loopback API and SQLite evidence store implemented in PR #97. Multi-tenant B2B identity, remote hosting, SSO/SCIM, company data separation and production privacy controls are not yet implemented.

## Endpoints

### POST /api/learning/attempt

Accepts a learner attempt:
- pseudonymous learner ID;
- stable attempt ID for idempotency;
- canonical idea ID, problem ID and version;
- evidence dimension and rubric score from 0 to 1;
- session ID and rubric version;
- structured response or learner work;
- optional evidence reference, transfer flag, delayed flag and submission timestamp.

Attempts are append-only. Replaying the same attempt ID and content is idempotent; reusing it with different content is rejected. The API stores learner work in SQLite and writes only a metadata summary to the general Merlin event ledger. For the current objective problems, the server maps problem IDs to versioned scoring rubrics and computes the score from the response; browser-supplied score, idea ID and dimension claims are ignored.

### GET /api/learning/learner?learner_id=...

Returns per-idea, per-dimension estimates, uncertainty, observation counts, independent session counts and state. It does not collapse all ability into one opaque score.

### GET /api/learning/recommendation?learner_id=...

Returns a lesson recommendation and reason trace: prerequisite readiness, target-skill estimates, uncertainty and recommendation-only authority. Optional curriculum_id scopes selection to mathematics or b2b-ml-agentic-ai.

## Evidence model

A uniform Beta(1,1) prior is combined with server-scored rubric results as fractional evidence. This is a transparent baseline estimator, not a validated cognitive diagnosis or calibrated psychometric model. A skill is unobserved until evidence exists. Provisional mastery requires multiple observations across at least two sessions and a minimum posterior mean. Retention additionally requires delayed and transfer evidence.

The current objective rubrics cover the rotation coordinate calculation, rotor half-angle recognition, invoice approval boundary and precision/recall calculation. Constructed explanations still require a separately reviewed rubric; they are not silently scored by an LLM. The estimator is intentionally easy to inspect and replace. Production calibration requires task-specific rubrics, item difficulty calibration, held-out cohorts, fairness analysis and comparison with human expert judgments. Do not use the present numeric threshold for employment decisions or high-stakes certification.

## Hermes connection

The mathematical curriculum graph is loaded from the canonical merlin-mathematical-idea-catalog.v1.json, using its lesson metadata and prerequisite IDs. B2B machine-learning and agentic-AI objectives are stored in MERLIN_B2B_LEARNING_GRAPH_V0_1.json. The API accepts curriculum_id=mathematics or curriculum_id=b2b-ml-agentic-ai.

When MERLIN_OUTBOX_DB_PATH points to the existing durable outbox, the API publishes:
- merlin.learning.attempt
- merlin.learning.recommendation

HermesLearningRouter consumes those topics using the existing leased, retryable, acknowledged outbox protocol. The learning handler records attempts idempotently and calculates recommendations from the same learner store and canonical idea graph. The existing research Hermes worker does not automatically subscribe to these learning topics; a dedicated learning router must be started or scheduled. This separation prevents learning events from entering research execution stages.

## Local run

The current Merlin API binds to loopback only. Configure:
- MERLIN_DB_PATH for the main event ledger;
- MERLIN_LEARNER_DB_PATH for the learner attempt database (defaults to the main SQLite file);
- MERLIN_OUTBOX_DB_PATH for the existing Hermes outbox.

Start the existing Merlin API process and use the lesson from the same origin. Do not expose this local MVP directly to a network or customer tenants. Add authentication, tenant isolation, authorization, rate limiting, data retention/deletion controls, encrypted storage, audit review and security qualification before B2B deployment.

## Design boundaries

- The learner model recommends instruction; it does not grade employees for HR purposes.
- Hermes lesson routing has recommendation-only authority.
- No lesson event grants tools, credentials, compute or production action authority.
- Business scenario values are synthetic training data unless separately sourced and labeled.


## Mathematics foundations course template

The canonical mathematics foundations course is versioned as `math-foundations-v1` and is loaded from `docs/merlin/MERLIN_MATH_FOUNDATIONS_COURSE_V1.json`. The loader cross-checks its objective IDs, prerequisite edges, dimensions, and lesson IDs against the canonical mathematical idea catalog before the API returns or applies the manifest.

Instructor-only endpoints:

- `GET /api/learning/templates/math-foundations` — preview the validated course template.
- `POST /api/learning/courses/{course_id}/templates/math-foundations` — apply the template to an existing draft course.

The apply operation uses the normal tenant-scoped `LearningPlatform.update_manifest` path. It does not create a course, approve it, publish it, enroll learners, or bypass independent review. The instructor must create the draft through `POST /api/learning/courses`; a separate reviewer must approve the version before publication.

The seven objectives map to canonical idea IDs `MATH-NT-001`, `MATH-NT-002`, `MATH-NT-003`, `MATH-ALG-002`, `MATH-COMP-001`, `MATH-LOG-001`, and `MATH-EXP-002`. The shared learner model therefore sees the same prerequisite graph whether recommendations are requested through the course endpoint or the global mathematics recommendation endpoint.

All assessments in this initial template are low-stakes and require human review. No learner answer, AI explanation, finite experiment, or lesson completion is promoted to formal proof or mastery by the template.


## Learner-controlled pathway and study preferences

Preferences are persisted in the existing `LearnerStore` database, in a separate `learner_profiles` table. They do not create a second learner database and are keyed only by the authenticated actor ID.

- `GET /api/learning/profile` — return the current learner's profile and safe defaults.
- `POST /api/learning/profile` — update pathway weights, interest tags, explanation modes, pace, and optional time budget.

Both routes require the authenticated actor to have the `learner` role. The API does not accept a learner ID in the request body; attempts to select another learner's profile are rejected. Profile changes are recorded in the event ledger using a hashed learner reference and profile digest, not raw preference content.

Supported pathways are `mathematician`, `mathematics_programmer`, and `computational_hacker`. Pathway weights are validated and normalized. Interest tags are normalized to lowercase underscore form. Pace presets map to bounded study windows (gentle: 20 minutes, standard: 35, intensive: 60, adaptive: no fixed cap).

Course and Hermes recommendations now use the persisted pathway weights, interests, and time budget in addition to the existing mastery/prerequisite evidence. Preference matching changes ranking only; it cannot change mastery estimates, lesson completion, or proof status. Score components and blocked-task reasons are returned for inspection.


The Merlin Learning web workspace exposes these controls without storing bearer tokens in browser storage: learners can adjust the three pathway weights, interest tags, and pace; instructors can apply the built-in mathematics foundations template only to an empty draft. Applying the template does not publish it.

The legacy `GET /api/learning/learner` and `GET /api/learning/recommendation` routes are also identity-scoped. They derive the learner ID from the trusted actor resolver; a supplied `learner_id` must match that actor or the request is rejected. These routes now use the same stored preferences as the course recommendation route.
