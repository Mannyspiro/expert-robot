# Merlin Forge: virtual GitHub

Merlin Forge is a local, durable repository service. It is intentionally independent of GitHub Actions, external repository accounts and remote Git hosting.

## Storage model

- SQLite stores immutable commit objects, mutable branch references, pull-request state and append-only event history.
- File bytes are stored as content-addressed SHA-256 blobs.
- A commit records a canonical tree and one or two parent commits.
- Pull requests capture source/target refs and are merged using a three-way comparison against the nearest common ancestor.
- Non-overlapping edits merge automatically. Conflicting edits return the exact paths and leave the target branch unchanged.
- Linear branches can be rebased onto another branch/commit. Rebase preserves original commits, creates replacement commits on the new base, and leaves the branch unchanged on conflict. Merge-commit rebases are rejected rather than guessed.
- Rollbacks move a branch reference to an existing immutable commit and append an audit event.
- The main branch is protected by default and requires exact-head `python.compile`, `python.unified_tests` and `hud.javascript_syntax` receipts before a virtual PR can merge. A successful check for an older commit does not satisfy the current PR head.
- Local CI records bind the exact commit, check name, declared runner ID, run ID and SHA-256 of the retained log. Check records and their log blobs are immutable, but the records are explicitly `UNVERIFIED` and have no promotion authority until authenticated CI/CACE receipt import is implemented. The declared runner ID is not an authenticated signer identity. CACE proof verification remains a separate independent gate and cannot be asserted through this generic local-check endpoint.
- Protected merges inspect the latest result for each required check on the live source branch head, not the PR's stale creation-time head. Every required result must be `success`, `verification_status=VERIFIED`, and `promotion_authorized=true`; missing, failed, malformed, legacy or unverified results block the merge; malformed metadata is treated as unverified rather than raising or being accepted. No public API can elevate a local check to verified.
- `integrity_report()` checks SQLite integrity, foreign keys, every content-addressed blob SHA-256/size, every commit identity, and referenced blob existence. `backup_to()` uses SQLite's online backup API, refuses to overwrite a destination, then verifies the copied database before returning success. This is a verified backup primitive; scheduled retention and production restore drills remain outstanding.
- `export_commit()` verifies every blob digest and materializes an exact commit into a new workspace directory with a bounded total size and a file/hash manifest. This is the materialization boundary for a future isolated headless runner; it does not itself execute code or provide an OS sandbox.
- Durable virtual CI jobs use an idempotency key, bounded retry count, leased claims, hashed fencing tokens, heartbeats, expiry recovery, immutable event history and retained SHA-256-checked logs. Job completion remains `UNVERIFIED` and cannot satisfy protected merge checks. The queue is a scheduler boundary, not an executor; worker authentication, sandboxed command execution and CACE receipt import remain separate gates.
- Runtime bootstrap now snapshots the allowlisted Python, tests, HUD, formal, Merlin documentation, research catalog/equation-atlas and workflow files into Forge. It excludes secrets by filename, environment files, generated caches, dependency trees, binaries and symlinks; bounded size/count overflow fails rather than silently truncating. Existing older Forge databases receive the new snapshot through a bootstrap virtual PR, never by bypassing protected `main`.
- SQLite writes serialize with BEGIN IMMEDIATE; branch updates compare the expected prior ref to prevent lost updates.

Hashes establish byte identity only. They do not prove code correctness, test success, safety or authorization.

## HTTP API

The API is served by Merlin's existing loopback-only application boundary. Check receipt writes are local-only in this initial implementation; a qualified runner/CACE transport is still needed to import remote receipts safely. Local receipts are an audit aid and merge guardrail, not cryptographic attestation.

| Method | Path | Purpose |
|---|---|---|
| GET | /api/forge/status | Branches, open PRs, recent events and runner state |
| GET | /api/forge/branches | Branch refs |
| GET | /api/forge/pulls | Pull-request records |
| GET | /api/forge/checks?commit=... | Check receipts for an exact commit |
| GET | /api/forge/jobs | Durable virtual CI queue |
| GET | /api/forge/jobs/{id} | Job state and unverified result |
| GET | /api/forge/jobs/{id}/log | Retrieve a retained job log and SHA-256 digest |
| GET | /api/forge/checks/{id}/log | Retrieve a retained CI log after SHA-256 verification |
| GET | /api/forge/events?limit=100 | Append-only event history |
| GET | /api/forge/file?ref=main&path=README.md | Read UTF-8 file and verify digest |
| POST | /api/forge/branches | Create branch from branch or commit |
| POST | /api/forge/commits | Commit path-to-content changes on unprotected branches; direct protected-main writes are rejected |
| POST | /api/forge/checks | Record immutable commit-bound local CI evidence, always unverified |
| POST | /api/forge/jobs | Enqueue an allowlisted check for an exact commit |
| POST | /api/internal/forge/jobs/claim | Authenticated worker claims a leased job |
| POST | /api/internal/forge/jobs/{id}/heartbeat | Authenticated worker renews its lease |
| POST | /api/internal/forge/jobs/{id}/complete | Authenticated worker returns result and retained log; remains unverified |
| POST | /api/forge/pulls | Open a pull request |
| POST | /api/forge/branches/{name}/rebase | Replay a linear branch onto another ref with conflict detection |
| POST | /api/forge/pulls/{id}/merge | Three-way merge or return conflict paths |
| POST | /api/forge/branches/{name}/rollback | Restore an existing commit ref on an unprotected branch; protected main requires a reviewed revert PR |

The application initializes the virtual repository from a bounded, secret-excluding source snapshot when no repository exists. Existing older databases receive a new source snapshot through a bootstrap PR rather than a direct protected-main write. The database is stored beside the configured event database as merlin-forge.sqlite3.

## CI and runner separation

Forge repository operations and queue operations do not execute code. The status response explicitly reports runner_execution=not_performed. A queued job or a worker's completed result is never represented as a test pass. The queue is durable and lease/fencing protected, but no sandboxed executor is currently connected.

CI must check out the exact commit, execute the pinned test suite, retain raw logs and machine-readable exit results, and upload evidence even on failure. Runner identity and qualification remain separate from repository state. CACE must independently verify execution receipts before any scientific/proof result is promoted.

## Current limitations

This implementation is a local single-node repository and durable CI queue, not yet a distributed Git replacement. It does not yet include patch review comments, signed commit identities, multi-tenant authorization, artifact retention/garbage collection, a sandboxed headless executor, scheduled backup retention or production restore drills. CI receipt ingestion is loopback-only and not yet bridged to GitHub Actions/OCI automatically. CACE independent receipt import remains unavailable. Those are subsequent acceptance gates; they must not be implied by the current API.
