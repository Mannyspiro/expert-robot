# Merlin learner-facing mathematics progress API v0.1

## Purpose

Expose the canonical zero-first Parrondo lesson to the existing loopback Merlin HUD. The API resolves lesson definitions on the server; clients can select only one of the three registered learning paths and complete only the current stage.

## Routes

- `GET /api/math/lesson?path=mathematician`
- `GET /api/math/lesson?path=mathematics_programmer`
- `GET /api/math/lesson?path=computational_hacker`
- `POST /api/math/lesson/complete` with JSON `{"path":"mathematician","stage_id":"play-the-games"}`

The GET response contains the canonical lesson, its stage prompts, current progress, and an explicit assessment boundary. The POST response returns the updated snapshot. Unknown paths, missing stage IDs, skipped stages, and replayed stages are rejected.

## Persistence and identity

Progress uses the existing `LearnerStore` SQLite schema in a separate database path. By default, if the event database is `events.sqlite3`, the learner database is `events.learners.sqlite3`. Set `MERLIN_LEARNER_DB_PATH` to override it. `MERLIN_LEARNER_ID` selects the server-owned local learner identity and defaults to `local-default`.

This loopback MVP is intentionally single-learner per server configuration. The browser cannot submit a learner ID or arbitrary lesson payload. Multi-user deployment requires authenticated identity resolution and per-user authorization before this endpoint is exposed beyond loopback.

## Evidence boundary

Completing a stage stores only a sequential progress cursor and completed-stage IDs. It does not create an `Attempt`, mastery record, spaced-repetition score, proof, or CACE receipt. Simulation outcomes and exploration progress remain distinct from assessed evidence.

## HUD

The Mathematics view now loads the saved lesson stage and offers a path selector for mathematician, mathematics programmer, and computational hacker. Completing the current exploration stage persists and advances the lesson. The independent Parrondo experiment remains available above the guided lesson.

## Validation

The focused API tests cover zero-first entry, canonical path isolation, sequential completion, persistence after reopening the store, and the absence of mastery credit. The CI workflow invokes this test module. A workflow definition is not proof of a successful run; verify the resulting GitHub Actions run before qualification.
