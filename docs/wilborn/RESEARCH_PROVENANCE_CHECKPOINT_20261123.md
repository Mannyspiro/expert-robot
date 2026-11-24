# Research provenance checkpoint — 2026-11-23

Parent: `40b672e2ee2a35efa1f06e5c79e418d42729544e`, draft PR #228. Its 65 tests and bounded live public probe passed. No real customer records or repository secrets were used.

## Change and experiment

An allowlisted URL, caller-supplied receipt, and matching bytes/hash are not proof of source authenticity. Label all research ingestion, extraction, tabular summaries, comparisons, snapshots and retrieval reports as unverified research input. Reject inconsistent byte identity at each analysis boundary, conflicting URLs for identical bytes in a batch, and malformed short CSV rows. Valid descriptive fixture calculations must still work.

Acceptance: all previous applicable tests and new regression cases pass on the new commit; live probe replays without upgrading source authenticity; report remains unverified. Do not interpret passing CI as real data verification, a qualified production network policy, or permission to deploy. Existing draft review and production gates remain.

Next: record actual new CI results, qualify trusted retrieval attestation, add independent source verification, and then evaluate business rankings against explicitly verified evidence.
