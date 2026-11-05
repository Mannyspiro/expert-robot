# Bidirectional CACE ↔ Expert Robot bridge

**Operational source of truth:** [AI runner and bridge operations](AI_RUNNER_AND_BRIDGE_OPERATIONS.md). Read that guide before dispatching or debugging. This page summarizes the trust boundary.

## Forward path

Expert Robot Avrea hosted runner → existing repository-scoped CACE-app SSH deploy key → isolated `executor/expert-robot-bridge` branch → CACE OCI ARM64 self-hosted runner (`self-hosted,cace,oci,aarch64`).

The Avrea dispatcher is a GitHub Actions runner, not a direct Avrea API client. It prefers `CACE_BRIDGE_SSH_PRIVATE_KEY` and falls back to the existing `RAILWAY_SSH_PRIVATE_KEY` alias. The latter is a CACE-app transport key, not a verifier credential. Do not regenerate, rename or expose it merely because the name is historical.

The OCI runner has `contents: read`, uses checkout with `persist-credentials: false`, and receives no Expert Robot reverse key. It performs bounded formal qualification and uploads structured evidence. It has no merge or promotion authority.

## Result contract and return paths

CACE emits result schema v3, including request/source identity, CACE repository/commit/workflow/run/attempt, pass/fail plus exit code, runner identity, pinned Lean/Mathlib, log digest/size, and qualification-only authority. A structured FAIL is a valid result and must be preserved.

The Avrea dispatcher polls the CACE bridge branch, validates the exact request ID and result/log digests, and uploads the returned evidence as an Expert Robot Actions artifact. This forward-polling path does not need the reverse SSH key.

The optional reverse path is separate. CACE Actions recognizes `EXPERT_ROBOT_SSH_PRIVATE_KEY`, `EXPERT_ROBOT_DEPLOY_KEY`, `CACE_TO_EXPERT_ROBOT_SSH_KEY`, or `EXPERT_ROBOT_DEPLOY_PRIVATE_KEY`. If configured, it writes a `cace-return/<request-id>` branch in Expert Robot; it does not merge. The reverse key was observed missing in the recorded run, so do not claim this path works until a real key is configured by an authorized maintainer and a run proves it.

SSH proves repository transport access only. It is not Ed25519 signer authentication. Current result envelopes remain unsigned until a trusted CACE signer is provisioned and independently verified against a trusted public key.

## PR creation and promotion

Expert Robot's `CACE Return PR` workflow is a separate path. A returned qualification result never merges automatically and never expands authority. `promotion_authority=false` is mandatory. A valid qualification FAIL is not a malformed envelope; it remains failure evidence.

## Base44

Base44 is a discoverable external integration only. This bridge does not deploy to Base44, invoke Base44 APIs, change Base44 configuration, or authorize paid resources.

Preserve the invariant: **Capability grows, authority never expands.**
