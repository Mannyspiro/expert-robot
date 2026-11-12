# OCI Runner Continuation Snapshot — 2026-11-11

This is a dated continuity record. It supplements, and does not replace, the main Merlin OCI handoff. It is not a live health check.

## Last known successful evidence

- GitHub Actions workflow run: `43094833635`.
- Reported runner identity: `cace-oci-a1`, runner ID `22`.
- Reported runner labels: `self-hosted,cace,oci,aarch64`.
- Reported inventory artifact: `merlin-oci-job-43094833635-1`.
- Reported artifact SHA-256: `105fc8ae395a4556831538e8d98a7c067158eff4107f9b3e30d4e25ed74a8aee`.
- Reported OCI MCP listener: loopback only, `127.0.0.1:8765` (documented MCP path: `/mcp`).
- Reported inventory snapshot: Oracle Linux 9.8, ARM64, 2 CPU cores, 10.64 GiB RAM, 29.43 GiB filesystem, approximately 0.48 GiB free.
- Reported MCP process/service was active at the time of that inventory.

These values describe the recorded workflow result only. They do not prove that the runner, VM, listener, free space, or registration is still current.

## Queued runs at the last handoff

The following runs were reported as queued with zero jobs; no execution or runner assignment was established:

- `43095312303`
- `43095650018`
- `43095559112` (PR #85 validation)

Do not infer that a queued run executed. Do not launch duplicate probes to try to force scheduling.

## Pull request state at the last handoff

CACE repository PRs #82 and #85 and the CACE gateway changes remained draft/unmerged/undeployed. The recorded PR #85 source head was:

`777a92a41a6081bd4330dd06082d7fb53a09ee17`

A prior CACE PR #83 revision was recorded at:

`85b007b8329c4cbbb55c5d6fb373ecb54779c973`

These are historical references and must be rechecked in the owning CACE repository before any further action. The CACE linked GitHub account was not available in the continuation session, so these PRs and their workflows were not re-read here.

## Current-session access boundary

- GitHub access to `Mannyspiro/expert-robot` is available.
- The linked account for `morganaspim/Cace-app` was not eligible in this session.
- No OCI MCP tools, SSH tool, OCI console, or general remote shell were exposed in this session.
- Attempts to look up the four run IDs under `Mannyspiro/expert-robot` returned GitHub 404, confirming those IDs do not belong to that repository/account context.
- No OCI command, MCP call, workflow dispatch, runner restart, installation, cleanup, cache mutation, provisioning, or cutover was performed in this session.

A Markdown handoff does not create access. Continue with repository-only work until the CACE GitHub account or an authenticated, read-only OCI MCP connection is actually available.

## Preservation and resource constraints

The last reported free space was approximately 0.48 GiB. Treat this as a severe capacity constraint until a fresh read-only check proves otherwise.

Do not:
- delete, overwrite, truncate, move, rename, chmod, clean, prune, or evict any OCI files or caches;
- install packages, run installers, prewarm Lean/mathlib, provision, restart, deploy, register, or cut over;
- copy complete runner directories, caches, model stores, or unknown trees;
- run duplicate or concurrent probes;
- place inventory output or archives on the OCI filesystem;
- expose credentials, SSH keys, tokens, environment files, or secret-store content.

Use `clean: false` for any future workflow that is separately approved and safe to run. Do not use historical workflow archives for cleanup, provisioning, service installation, watchdog, cache prewarm, or cutover actions.

## Next safe sequence

1. Restore the authorized CACE repository connection and re-read PRs #82, #83, and #85, their exact head SHAs, and associated workflow runs.
2. If the existing successful inventory artifact is still available, inspect its metadata and digest without dispatching another OCI job.
3. Re-establish MCP connectivity through the documented authenticated route; first perform protocol initialize, then tools/list, then only the read-only capability/health/instance/disk/job checks actually exposed.
4. If the MCP is reachable only on loopback, use an approved authenticated tunnel or existing runner gateway; do not expose port 8765 publicly.
5. Stop before any filesystem traversal, package install, or workload execution while free-space headroom is unknown or remains near 0.48 GiB.
6. Keep all new work in isolated branches and draft PRs. Do not merge, deploy, or promote without explicit approval.

## Relationship to Merlin

- Hermes decomposes and routes tasks, maintains durable outbox/idempotency/acknowledgements, and collects results.
- MCFC allocates worker leases, budgets, capabilities, telemetry, and resource accounting.
- OCI executes only bounded approved jobs; it is not an unrestricted shell.
- CACE independently verifies exact source/artifact digests and toolchain evidence.
- Avrea is a separate optional runner lane; the last recorded Avrea state was no credits, so do not assume it is available.
- RSI candidate generation, evaluation, held-out benchmarking, skeptical review, and promotion remain separate stages. Candidate generation must never grant execution authority or self-certify correctness.

No new verification claim is made by this document. It is a continuity and safety record only.
