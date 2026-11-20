# Branch research receipt isolation

Release preparation, November 20, 2026. Parent PR 183 source: b928e634ccce96907788d95a7d82bd58c93841a4. The user explicitly authorized push, merge and deployment after the local continuation packet. This document does not claim those operations have completed.

## Repair

Evaluator input previously aliased scheduler-owned prerequisite receipts. Overwriting a prerequisite hash or clearing the input mapping could commit a receipt which failed restart. Capture prerequisite and chronological links before evaluation and pass a recursive detached snapshot. Schema, scheduling, XP rules and authority are unchanged.

## Measured local evidence

The two original tests pass. With 19 new regression/boundary tests, original source has seven errors, a shallow-copy control four errors, and the selected repair passes all 21. The continuation packet also retains 120 matched deterministic graph/outcome scenarios. These are same-author synthetic checks, not independent scientific verification. The release preparation reran all 21 tests on Python 3.13.5 with zero errors or failures.

Source SHA-256: 78cc71d4b506a59bf7712a41193ae24644f98f6ec59024c82ae4d7855da7e3b5. New tests SHA-256: 34735ebc088b54f0e8f11d75871246dd215cabad15c0e0ee941092162adf905a.

Reproduce: `PYTHONPATH=python python3 -m unittest discover -s tests -p 'test_branch_research*.py' -v`.

## Release gates and limits

OCI exact-source execution is required before release. Preserve existing checks, grants, unit configuration, private state and rollback release. Do not use Avrea before December 1, 2026. Do not bulk-merge runtime PR 178 or its unrelated ancestors.

The callback is trusted in-process code; deep copying is not sandboxing. Forced interruption preserves committed checkpoints but can repeat external effects on retry. Do not enable remote side effects without explicit idempotency/reconciliation. The legacy `verified` field means a local evaluator pass, not CACE verification, scientific truth or promotion. Canonical registry integration and full-platform production acceptance remain separate gates.
