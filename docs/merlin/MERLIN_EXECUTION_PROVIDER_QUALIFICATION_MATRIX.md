# Merlin execution provider qualification matrix

**Status date:** 2026-11-06  
**Purpose:** distinguish source adapters, test transports, CI runners, cloud control planes and production execution providers.

## Current evidence

| Provider | Observed capability | Evidence | Qualification state |
|---|---|---|---|
| GitHub Actions | Hosted compile and test jobs with logs/results artifacts | Integrated Merlin workflow run 42271108562, exact head `7ca317530ef8d8f0c1fd33fb22390d425bec6d82`, 117 tests passed; artifact 13529366667 | Qualified for this CI test workflow only; not a general production compute worker |
| Avrea | `AvreaAdapter` supports injected dispatch/collect transports, approval and MCFC lease checks, artifact storage and result receipts | `tests/test_avrea_adapter.py` uses injected fake transports; Avrea-specific hosted workflow attempts in this branch were cancelled | Adapter contract tested; live Avrea transport and runner unqualified/unavailable |
| OCI in `morganaspim/Cace-app` | `ops/oci_mcp` is a narrow MCP control plane using OCI instance principals; loopback HTTP endpoint; read-only default; exposes CACE runtime health/logs, instance summary, VNIC/attached NSG inspection and separately gated service restart/network-rule operations | Current `main` source: `ops/oci_mcp/README.md`, `server.py`, `policy.py`, `cace-oci-mcp.service` | OCI operations control plane exists in source; it is not a compute job runner or Merlin execution transport |
| OCI runner/provisioning workflows | OCI VM provision, runner health, service install/watchdog and cutover workflows appear under `.github/workflow-archive/` | Recursive Git tree of `morganaspim/Cace-app` main; active `.github/workflows/` listing contains no corresponding OCI runner workflow | Archived; do not infer an active runner from these files |
| CACE verifier | Merlin adapter accepts an injected verification transport and validates exact-input receipt fields, signer identity and receipt digest | `tests/test_cace_adapter.py` uses test transports | Contract tested; no live authenticated CACE verification endpoint/transport verified |
| Merlin local worker | Hermes worker consumes the task topic, validates approval/MCFC lease, enforces resource budgets, heartbeats, observes cooperative cancellation and stores bounded results | `tests/test_hermes_worker.py` and unified hosted evidence | Worker logic tested; no production supervisor/hosted worker process deployed |

## OCI access clarification

The CACE repository's OCI MCP server is designed as a deliberately narrow control plane, not a generic shell and not a general OCI SDK proxy. It runs on `127.0.0.1:8765` and uses OCI instance principals. The service's documented tools are for CACE service/runtime inspection and a small set of separately enabled operational actions. It does not expose a compute-job submission/collection interface for Merlin.

The repository's OCI provisioning and runner-health workflow files are archived under `.github/workflow-archive/`. They are historical implementation assets, not active workflows. The current ChatGPT GitHub connection can inspect the repository source, but it does not provide an authenticated connection to the OCI VM's loopback MCP endpoint. No OCI MCP tools or Oracle OCI connector were available in this session's connected tool inventory/plugin discovery.

Therefore, Merlin must not report OCI as an available runner until the OCI service is deliberately exposed to Merlin through an authenticated, supported MCP/HTTPS bridge and a harmless capability probe returns a verifiable runner identity and execution receipt.

## Next qualification sequence

1. Establish the intended OCI endpoint/connection through a supported authenticated remote MCP or HTTPS gateway; keep the loopback service private and do not publish an unauthenticated endpoint.
2. Confirm whether the target is a CACE service operations plane or a dedicated OCI compute runner. Do not conflate them.
3. If a compute runner is intended, define a narrow job API separate from the operations MCP: submit immutable job manifest, return job ID, report status, stream bounded logs, collect artifacts and resource metrics, and support cooperative cancellation.
4. Bind every result to exact source commit, artifact digests, tool versions, environment, resource limits, start/end timestamps, exit status and runner identity.
5. Run a harmless no-shell capability probe, then a bounded deterministic computation, then a reproducible test job. Preserve failed, unavailable, cancelled and no-credit outcomes.
6. Require independent CACE verification of the exact returned artifacts before capability qualification or research/proof promotion.

## Decision rule

A provider is not qualified merely because its adapter class exists, its VM is provisioned, its OCI instance principal authenticates, a service health endpoint responds, or a workflow file exists. Qualification requires a live end-to-end run with independently checkable, source-bound execution evidence.
