# Merlin OCI Runner Agent Skill

Use this guide when an AI agent needs to understand or work with the Merlin OCI runner through an approved MCP connection.

## Mission

Help build and operate production Merlin using the existing project resources while preserving the OCI runner and all existing contents. Work incrementally, use evidence, and submit repository changes through pull requests. Do not merge or deploy without explicit approval.

## Architecture map

- **Expert Robot** — Merlin application, orchestration, research, cognition, agent interfaces, RSI, math learning, and cross-system integration.
- **CACE** — independent verification, formal proofs, evidence receipts, reproducibility, and qualification.
- **Hermes** — task decomposition, routing, durable outbox, idempotency, acknowledgements, deadlines, cancellation, and result collection.
- **MCFC** — virtual compute/module fabric, capability registry, leases, budgets, workers, telemetry, and resource accounting.
- **Avrea** — optional external runner lane; use only when currently configured and evidenced.
- **OCI** — existing CACE ARM64 runner; preserve its current files, jobs, caches, and configuration.
- **Engineering** — FreeCAD/CAD, engineering IR, wiring/netlists, electrical checks, ngspice, and reproducible simulation.
- **Media** — image/video generation outputs are versioned assets; they are not editable CAD or proof of engineering correctness.
- **Learning** — mathematician, mathematics programmer, and computational hacker paths; concrete experiments before abstraction, then proofs/algorithms and retrieval practice.

## Connection truth

A Markdown file does not grant access. The agent must have an actual connected MCP client and an authorized remote or local transport. The existing CACE OCI MCP currently exposes a narrow set of read tools; it is not an SSH shell or general filesystem browser. Never claim live access based on repository documentation or historical conversation notes.

## Mandatory OCI sequence

1. Confirm that the MCP connection is actually present and identify the exact tool names available in this session.
2. Read capability switches.
3. Confirm instance OCID, region, hostname, architecture, and lifecycle state.
4. Read free disk space and inode headroom.
5. Inspect active runner jobs and service state.
6. If identity, headroom, or active-job status is unknown, ambiguous, or unhealthy, stop.
7. Perform bounded metadata-only inventory of explicitly approved roots.
8. Exclude credentials, private keys, tokens, environment files, secret stores, shell histories, and sensitive runtime data.
9. Retrieve only individually selected, non-secret, bounded files.
10. Store manifests and artifacts outside the OCI disk, preferably in a new Git branch and PR.

## Preservation rules

- Never delete, overwrite, truncate, rename, move, or chmod existing OCI content.
- Never run cleanup, cache eviction, installer, package installation, provisioning, restart, deployment, prewarm, or cutover operations without separate explicit approval.
- Never copy entire runner directories, caches, model stores, or unknown trees.
- Never stage inventory output on the OCI filesystem.
- One OCI operation at a time; bounded time, depth, entries, and bytes.
- Do not expose or copy secrets into GitHub, logs, chat, or skill files.
- If a destination file already exists, choose a new path; do not replace it.
- A content hash proves byte identity only, not correctness or qualification.

## Repository workflow

1. Inspect the target repository and current branch.
2. Create an isolated branch from the current base.
3. Add new files rather than replacing existing files.
4. Review diffs and check for accidental secrets.
5. Run only relevant bounded tests; do not start expensive OCI/Avrea jobs without checking budgets and current job state.
6. Open a draft PR with exact scope, commit, test status, and operational effects.
7. Never merge or deploy without explicit user approval.

## Evidence discipline

Distinguish clearly:
- repository source inspection;
- local/fake tests;
- GitHub Actions results;
- live OCI MCP responses;
- independent CACE verification.

Do not call a simulated result a live result. Do not call a hash, model assertion, or successful transport a proof. Qualification receipts must bind source repository and commit, artifact digest, toolchain/version, execution details, and independent CACE result.

## When tools are missing

If no connected OCI MCP tools are exposed, continue useful repository-only work and state that live OCI access is unavailable. Do not ask the user to paste private keys into chat. Rotate any key that has been disclosed in chat before using it again.

## Required completion report

Report:
- repository and branch;
- PR URL and commit SHA;
- files added/changed;
- tests actually run and their result;
- live OCI actions actually performed (or explicitly none);
- whether any existing OCI files or caches were changed (must be no for inventory tasks);
- blockers and next ranked action.
