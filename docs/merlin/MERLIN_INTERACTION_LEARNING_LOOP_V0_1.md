# Merlin Interaction Learning Loop v0.1

## Purpose

Merlin should improve from real use: which tasks people attempt, where they succeed, where they correct Merlin, which tools fail, which workflows are abandoned, and which features repeatedly cause friction. This is a continuous measurement and evaluation system, not a permission for uncontrolled self-modification.

## Signal layers

1. **Operational telemetry (automatic, metadata-only):** route, method, status code, duration, response size, component, model/provider identifier where configured, and evidence references. Request/response bodies are not copied into the telemetry stream. Existing event storage hashes request metadata rather than persisting the original request body.
2. **Explicit task feedback:** a client may submit an opaque session ID, task category, domain, outcome (success/partial/failure/abandoned), optional categorical friction and correction labels, and optional 1–5 satisfaction score. Free-text prompt, response, attachment, credential and transcript fields are ignored and never copied to this feedback table.
3. **Evidence-backed learning signals:** educational attempts remain in the separate learner ledger, with server-owned rubric scoring, skill dimensions, problem version, session independence, delayed retention and transfer evidence.
4. **HUD interaction telemetry:** view changes, task submission categories, voice-input starts, attachment requests and explicit outcome feedback are sent as categorical operator events. The browser never includes prompt text or voice transcripts in these events.
5. **Execution and verifier telemetry:** Hermes, MCFC, Avrea and CACE sources remain distinct; simulation events are not production execution evidence. A tool result is not proof until the relevant verifier has checked its exact artifact.

## Current API surface

- GET /api/learning/preferences
- POST /api/learning/preferences
- POST /api/interaction/feedback
- DELETE /api/interaction/feedback?session_id=OPAQUE_SESSION_ID (removes categorical feedback for that session only)
- GET /api/learning/improvements
- POST /api/learning/improvements/evaluate (stores a content-addressed, aggregate-only evaluation snapshot)
- DELETE /api/interaction/feedback?session_id=OPAQUE_SESSION_ID (removes categorical feedback for that session only)

Preferences: aggregate_telemetry controls metadata-only HTTP-boundary measurement; explicit_feedback_learning controls acceptance of voluntary categorical feedback; personalization is reserved and defaults off; raw conversation retention and automatic code/policy modification remain disabled.

## Analysis rules

- Route and task metrics are aggregate, not user rankings.
- A proposal requires at least five observations by default.
- Reliability proposals require at least a 10% server-error rate.
- Performance proposals require p95 route latency of at least 1.5 seconds.
- Task-quality proposals require at least 25% failure/abandonment or mean satisfaction below 3/5.
- Each proposal exposes its sample count, observed reason and recommended measurement.
- Small samples produce no recommendation; missing data is unknown, not zero.

## Improvement lifecycle

observe → normalize → aggregate → propose → held-out evaluation → human review → canary → compare → approve or roll back

The analyzer only emits proposals. It cannot edit source, deploy, alter policy, expand permissions, dispatch agents, or promote a capability. Improvements require a versioned hypothesis and baseline; held-out tasks; paired before/after measurements and uncertainty; regression, privacy, safety and cost checks; independent verification where artifacts/proofs are involved; explicit approval for deployment and rollback readiness.

## Privacy and governance

- Use opaque, scoped session IDs; do not put email addresses or names in identifiers.
- Do not collect raw chat text, voice recordings, images, documents or credentials for interaction analytics.
- Store only categories and measurements required to explain a proposal.
- Keep user-level personalization separate from cross-user aggregate analytics.
- Honor telemetry and feedback opt-outs.
- Preserve source separation and evidence provenance.
- Never infer sensitive personal traits from interaction patterns.
- Do not train a model or update prompts from an isolated correction without review.
- Do not treat engagement, session length or clicks as proof of task success.
- Capability can grow only through qualification; authority does not expand.

## Known implementation boundary

v0.1 provides metadata telemetry, explicit categorical feedback, configurable opt-outs, aggregate quality/performance analysis, content-addressed evaluation snapshots and recommendation-only proposals. The HUD now emits metadata-only view/task/voice/attachment events and exposes Worked / Partly / Did not work feedback controls. It does not yet implement cross-session personalization, raw-content learning, automated model fine-tuning, automatic prompt/code changes, a canary deployment controller, or user-facing data export/deletion workflows. These remain separately gated engineering work.