# Merlin Evidence Receipt Contract v0.1

## Purpose
A receipt binds a reproducible computation to the exact input files, source code, environment, revision, command, and output bytes. It records what ran; it does not certify that the model is physically true.

## Current implementation
`python -m merlin.equation_atlas.receipts` writes a JSON receipt for an existing artifact. It records:
- receipt schema version and UTC creation time;
- explicit claim scope;
- Git commit and ref when supplied by GitHub Actions;
- command and Python/platform metadata;
- SHA-256 hashes of declared source files;
- output artifact SHA-256 and byte count;
- explicit limits on what the receipt proves.

The CI job hashes the legacy normalized tranche, canonical entry schema, receipt schema, dependency lock, normalizer, dimensional checker, symbolic checker, numerical baseline implementation, and generated canonical normalized tranche. It publishes the numerical baseline, canonical normalized tranche, and receipt together.

## Verification semantics
- Hash equality means byte identity for the hashed file, not correctness of its content.
- A successful deterministic run means the declared program completed in the recorded environment.
- Synthetic baselines are not empirical validation.
- A receipt does not prove a Lean theorem.
- A source hash does not replace a bibliographic citation or exact supporting passage.

## Append-only policy
Receipts are immutable evidence records. A correction or rerun creates a new receipt with a new timestamp, commit and artifact hash. Do not edit historical receipts in place. A future registry should link superseding receipts without deleting the original.

## Planned extensions
1. Add a separate digest for the test log and record per-test outcomes in the receipt.
2. Include dependency lockfile hash and OS/container image digest.
3. Record random seeds, numerical tolerances, solver settings and test output digest.
4. Bind each experiment to exact equation-entry IDs and versions.
5. Add signed attestations only after key management and trust policy are defined.
6. Store receipts in the project evidence registry with independent reviewer state.

## Security and authority boundary
Research workers may create candidate receipts and artifacts. They may not promote evidence status, merge protected branches, or expand permissions. Those decisions remain approval-gated.
