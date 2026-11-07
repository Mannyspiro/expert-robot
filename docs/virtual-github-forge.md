# Merlin Virtual GitHub Forge

## Decision

The Virtual Forge is Merlin's intended primary development control plane.
GitHub remains an optional remote adapter for import/export, provenance and
human collaboration. Normal engineering iteration must not depend on opening a
GitHub PR or receiving a GitHub-hosted CI runner.

## Implemented core

The initial implementation is in `python/virtual_forge.py`, backed only by
Python's standard library and SQLite:

- immutable content-addressed file blobs and commit snapshots;
- named branches with optimistic expected-head checks;
- commit ancestry and common-ancestor discovery;
- pull-request records internal to the Forge;
- three-way file merge, including non-overlapping line edits and explicit
  conflicts for overlapping changes;
- merge commits with both parent identities;
- rollback by creating a new commit that restores a prior snapshot;
- append-only, hash-chained Forge event history;
- idempotent worker-job enqueueing, priorities, leases, expiry/reclaim,
  attempt counts, worker ownership, result records, logs and artifact digests;
- workspace snapshot export with path traversal checks.

The CLI is `python/forge_cli.py`. It supports status, branch creation,
commits from files, internal PR creation/merge and workspace export.

## Operating model

```text
Merlin research / agent proposal
             |
             v
     Virtual Forge branch
             |
             v
    isolated workspace export
             |
             v
       internal job queue
             |
             v
   leased build/test worker
             |
             v
  logs + artifacts + digests
             |
             v
    CACE independent review
             |
             v
 internal PR / controlled merge
             |
             v
    immutable Forge history
```

The Forge database process does not execute source code. Worker jobs are
separate from the Forge transaction layer. A worker must use a dedicated,
resource-limited execution environment and must not inherit repository
credentials or unrelated host authority. The queue and lease protocol are
implemented; a production sandboxed worker runtime is still a qualification
gate.

## Current boundaries

- SQLite commit/event hashes establish identity and tamper evidence, not truth.
- A successful merge is a source-control operation, not proof that tests pass.
- A completed job is not trusted merely because its worker reports success.
- CACE must independently verify the exact artifact digest and execution
  evidence before any result is promoted.
- The current SQLite store is a single-host foundation. Multi-host replication,
  authenticated remote workers, quota enforcement and crash-recovery testing
  remain future work.
- The CLI currently creates commits from supplied files; full interactive
  Forge UI, editor integration and automatic agent dispatch remain future work.
- GitHub PR #119 is still a draft integration/export artifact, not the Forge's
  primary change-management mechanism.

## Initial verification suite

Run locally:

```bash
python3 -m unittest discover -s tests -p 'test_virtual_forge.py' -v
```

The same test is included in repository CI. It has not yet produced a
successful run on the currently available runner infrastructure.
