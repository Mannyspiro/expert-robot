# Research runner checkpoints

The session preference effective 2026-10-07 16:37 America/Phoenix is to use
commits sparingly, aiming for about 20 per day. This is a batching target,
not a reason to create 20 commits or rewrite earlier history. Tested code and
workflow changes belong in meaningful commits. Progress and validation status
are recorded by runners, without a commit for each update.

CI reuses its existing runner to write `research-checkpoint.json` and a SHA-256
manifest, then uploads `research-runner-state-<run-id>` with 30-day retention.
The record includes the source head, execution commit, producer run, time,
session preferences and current-head workflow results. On a pull request,
the execution commit can be GitHub's merge commit while the source head is
the PR commit. No credentials or environment dumps are stored.

The separate PR-47 maintenance job can cancel only superseded, unassigned
validation runs on `research/magick-ir-v0-1` in this repository. It checks the
current PR head and job assignment again before each standard cancellation.
It preserves current-head runs, assigned jobs, unrelated workflows and RSI
generation. Its Actions-write permission is confined to this administrative
job; it has no Contents-write permission or proof/promotion authority. The
shared Avrea concurrency slot and half-month budget gate remain in place.

Research validation now uses existing GitHub-hosted Ubuntu runners, serialized
through `expert-robot-research-validation-slot`. This includes full C++ CI,
the pinned Lean qualification job, CACE integration and symmetry checks. The
L3 policy permits this free fallback with the same verifier and no promotion
permission. Specialized Avrea/RSI lanes retain their original budget gates.
Historical research workflow entries and timeout estimates stay in Avrea
accounting; moving a workflow cannot erase its earlier spending. Only jobs
positively identified as GitHub-hosted are excluded from Avrea charges.
Full CI and formal qualification both retain source-bound checkpoints.

To resume, inspect the latest completed checkpoint artifact for the intended
source head. Verify its manifest hash and compare the recorded workflow links
with live results, since another workflow may have finished after the snapshot.
Artifacts expire after the requested retention period; export any irreplaceable
evidence before expiry. Compiler and dependency caches hold rebuildable data
and can be evicted. Neither checkpoints nor cache hits qualify or promote
research results. Capability grows, authority never expands.
