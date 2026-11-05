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

Attempts are append-only. Replaying the same attempt ID and content is idempotent; reusing it with different content is rejected. The API stores learner work in SQLite and writes only a metadata summary to the general Merlin event ledger.

### GET /api/learning/learner?learner_id=...

Returns per-idea, per-dimension estimates, uncertainty, observation counts, independent session counts and state. It does not collapse all ability into one opaque score.

### GET /api/learning/recommendation?learner_id=...

Returns a lesson recommendation and reason trace: prerequisite readiness, target-skill estimates, uncertainty and recommendation-only authority.

## Evidence model

A uniform Beta(1,1) prior is combined with rubric scores as fractional evidence. This is a transparent baseline estimator, not a validated cognitive diagnosis or calibrated psychometric model. A skill is unobserved until evidence exists. Provisional mastery requires multiple observations across at least two sessions and a minimum posterior mean. Retention additionally requires delayed and transfer evidence.

The estimator is intentionally easy to inspect and replace. Production calibration requires task-specific rubrics, item difficulty calibration, held-out cohorts, fairness analysis and comparison with human expert judgments. Do not use the present numeric threshold for employment decisions or high-stakes certification.

## Hermes connection

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
