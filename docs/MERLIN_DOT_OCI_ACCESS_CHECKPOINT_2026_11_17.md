# Merlin dot OCI access checkpoint — 2026-11-17

Status: live bounded GitHub-to-OCI access confirmed. This is operational evidence, not production qualification or mathematical proof.

## Verified live checks

| Check | Run | Exact request commit | Result |
|---|---|---|---|
| Runner inventory | https://github.com/morganaspim/Cace-app/actions/runs/44134642694 | d2896d7fcdba538838d43995cb1f7c43e2f7ca72 | SUCCESS |
| Read-only MCP probe | https://github.com/morganaspim/Cace-app/actions/runs/44134776966 | 502a228e795174a39e8622c1a82ded2f15b62972 | SUCCESS |

Both jobs ran on cace-oci-a1, runner ID 22, labels [self-hosted, cace, oci, aarch64]. Collected November 17 at approximately 10:14 AM America/Phoenix.

- Oracle Linux Server 9.8; ARM64; 2 CPUs; 11,427,774,464 bytes RAM (about 10.64 GiB).
- Filesystem: 131,894,083,584 bytes total; latest check 104,747,753,472 bytes free (about 97.55 GiB). Historical 0.5 GiB warning is stale.
- Runner listener and systemd unit active.
- cace-oci-mcp active; MCP listener remains loopback-bound.
- MCP initialize/tools-list succeeded using protocol 2025-03-26.
- get_cace_runtime_status returned active=true, reachable=true, HTTP 200, service CACE Studio/status ok.
- get_control_capabilities reported service_restart_enabled=false, network_write_enabled=false, generic_shell_exposed=false, secret_access_exposed=false.
- get_github_runner_status is NOT deployed. Its newer repository implementation must not be assumed installed.
- Deployed tools do not include candidate attestation issuance/verification. Successful execution is not an independent CACE-signed attestation.

## Access route

CACE request branch: merlin/oci-jobs/dot-inventory-20261117-9ad43183.
Reviewed base: f91f9a945dd2ae1ea287949baa9f1a3133785f1b (CACE PR #99).

The existing .github/workflows/merlin-oci-job-gateway.yml executes fixed profiles from a push that adds/modifies exactly one strictly typed request JSON under merlin/oci-requests/. No SSH credential is required. The gateway is on reviewed feature/job branches, not main; PR #86 merged into the runner-inventory feature branch.

Only inventory_snapshot and mcp_readonly_probe were invoked in this continuation. The inventory was collected by the gateway's pinned module, separately from the deployed MCP's absent runner-status tool. These are indirect runner operations via GitHub, not a direct ChatGPT MCP connection.

## Artifact integrity

Downloaded ZIPs were independently SHA-256 checked against GitHub artifact metadata:
- Inventory: ee6d6c9fdf576178fc064bfae911bf61313fb58b579144571ee36fd6a0c55631.
- MCP probe: 777b11e39bb2fd0e095e7db0d3d1e70653bdeaeedbdf2cc9e9ddb9b5a5c6af3b.

Retain receipts after the upstream Actions artifacts expire December 1, 2026.

## Effect and limits

Two additive request files were committed to an isolated CACE job branch. The runner created small unique temporary receipt/artifact directories and uploaded artifacts. No existing source/cache cleanup, package installation, service restart, network-policy change, merge, deployment, secret read, signing or promotion was performed. The old direct-SSH network failure does not invalidate the proven GitHub runner route.

This probe does not establish current OCI instance OCID/region, inode headroom, installed dot dependencies, real model/evaluator transport, a live identity provider, or direct ChatGPT MCP registration.

## Continuation order

1. Reuse this proven GitHub gateway for bounded approved operations; do not request or reuse the photographed SSH key.
2. Prepare an exact-source validation profile for the dot bridge at Expert Robot commit 703b21e3639c239484e851bebdb1a60c755d4924. Existing allowlisted gateway profiles do not accept arbitrary dot tests. Check host Python/dependency compatibility before choosing an execution environment; do not install packages implicitly.
3. Keep the prepared dot research request 87a2b430ffd3f300e6c92ebf0502aedee7ffad6f794f1fbe18f20f672b532353 pending review; neither probe dispatched it.
4. Connect the private dot read plane using real host-owned identity configuration and a private authenticated transport; no such endpoint was provisioned by these checks.
5. Connect two real coder adapters plus an independent held-out evaluator behind existing Hermes/MCFC gates. Keep signing, qualification and production promotion separately controlled.

No code changed, so the previously reported 74 local dot tests were not rerun and are not claimed as OCI tests.
