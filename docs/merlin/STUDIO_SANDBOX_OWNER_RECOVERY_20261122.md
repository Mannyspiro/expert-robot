# Merlin Studio owned sandbox recovery — native checkpoint, 2026-11-22 (UTC 2026-11-23)

**Status:** Real Docker crash/restart recovery verified on GitHub's ephemeral Linux runner. This branch is still **a draft candidate, not a production release or approval to deploy**.

## Original defect and independent witness

An actively executing Python script can survive termination of the Studio process that requested it. Prior Studio recovery marked an unfinished run "interrupted" and rejected replayed approvals, but that **did not terminate the still-running remote sandbox**. Controller-side resources and their cleanup status must be verified independently of Studio's conversation status.

[Draft PR #215](https://github.com/Mannyspiro/expert-robot/pull/215) at source SHA ffd965ce3a72c7d4dbf9c8f030a82affc8ceab70 adds durable ownership and a real process-crash test. Based on [#213](https://github.com/Mannyspiro/expert-robot/pull/213) and its previously verified approved execution, active cancellation, and restart tests.

**Proof:** [Native run 45101573240](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573240), [JSON/source and server-log evidence artifact 14785108319](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573240/artifacts/14785108319) (expires December 7, 2026). The test:
1. Started Studio with an explicitly configured local OpenSandbox controller and an immutable image.
2. Created and approved a 90-second script through the actual HTTP API; Docker top independently observed the running remote Python process.
3. Verified the owning run ID and script hash had already been durably recorded in Studio SQLite.
4. Killed only the **temporary test Studio server** with SIGKILL, verified its remote sandbox was still live, then restarted Studio with the same data directory.
5. Verified a persistent owner-metadata match, remote deletion, no residual managed containers/volumes, no pending intents, interrupted original run, rotated session token and rejected replay of old approval. No inference model or user data was involved.

The native workflow independently reconfirmed deny-all egress to a controlled canary, CPU/memory/PID restrictions, no unexpected host mount, bounded timeout, live ToolSet execution, normal HTTP approval/denial, and HTTP active cancellation. A controller-side outage **was simulated in unit tests**, not observed as a complete real controller failure/recovery sequence.

## Implementation boundaries

- Store.sandbox_owner() persists one opaque, random 128-bit owner identity **inside the existing SQLite data directory**, not in a new external registry.
- Store.sandbox_reserve() writes a source-hash-bound intent **before** the SDK can create a remote container. Its stable run_id is the canonical run identity.
- execute_approved() passes this owner and run ID as remote sandbox metadata, without inserting credentials or original user prompt text into metadata.
- An OS advisory lock prevents multiple Studio server processes from claiming the **same data directory** while sandbox mode is selected.
- Startup with pending intents uses the pinned OpenSandbox manager to list bounded pages of records filtered by owner metadata. Each returned record is independently checked for exact ownership. Only these matching records can be killed, and the tool remains disabled until the control plane reports no live owned records.
- Normal completion checks only that **its own run's** remote sandbox is no longer live, without terminating a sibling task from a concurrent run.
- A controller failure, ownership mismatch, pagination overflow or unverified cleanup retains durable intents and disables run_python, with a recovery status returned by the existing Studio status endpoint. No fallback to host Python occurs.
- Host Python remains the original default. The source-only ZIP adds sandbox_recovery.py but does not auto-install Docker, OpenSandbox SDK, weights, keys, or permit remote network traffic.

## CI evidence and controls

- [Studio and portable gates 45101573386](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573386): success. **8 Studio opt-in tests**, **11 new owner/recovery tests**, **4 cancellation tests**, **9 existing optional OpenSandbox/Z.ai tests** all passed. Source-only ZIP identity and extracted offline startup/restart passed. [Portable package/receipt 14785981177](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573386/artifacts/14785981177).
- [Experimental self-healing 45101573356](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573356): success.
- [Native Docker 45101573240](https://github.com/Mannyspiro/expert-robot/actions/runs/45101573240): success, includes actual Studio process SIGKILL and live orphan observation.
- Generic CI workflow 45101573235 was **cancelled** under its concurrency rules; it is not evidence of a full generic CI pass.
- Other unrelated CI/host configurations are not inferred from these results.

## Known limits and next production gate

1. The controller outage and restoration of **live pending** sandboxes has not yet been exercised against an actual stopped/restarted controller. Unit tests cover this condition, and new sandbox work fails closed if reconciliation cannot be confirmed.
2. If control-plane metadata is missing, malformed or unavailable, recovery remains blocked. Source created by **older untagged prototypes** is not discoverable by this owner-scoped algorithm.
3. The control plane's "no live records" observation is not an independent general proof of kernel isolation or absence of every resource; Docker-based inspection covered one ephemeral host.
4. Owner identity is scoped to a writable Studio **data directory**. Copying a data directory to multiple concurrently running machines, using unreviewed controllers, or bypassing the single-host lease requires separate operating procedures and is not qualified.
5. Studio's HTTP Cancel currently acknowledges the request before the remote controller finishes cleanup; the user interface may report a terminal cancelled state prematurely when the controller fails. **Next repair:** represent "cancelling" separately from "terminated", preserve cleanup-pending evidence and only show successful cancellation after confirmation.
6. Run these exact verified source/runtime revisions on the approved OCI or desktop target, test controller loss/restoration, concurrency, long-running workloads, and rendered browser approval UI. A signed, reviewed release depends on explicit approval and PR dependency reconciliation.

### Skeptical-scientist framing

Hypothesis: a durable pre-create intent and controller owner metadata can close the gap between local run recovery and actual remote cleanup. **Observed**: a truly orphaned Docker script survived Studio SIGKILL and was terminated on restart; pending intent and approval were not replayed. Competing mechanism: network/controller outage or metadata inconsistency could prevent authoritative cleanup. Falsifier: any foreign sandbox killed, approved code executing without a pre-create record, a pending owner showing python_sandbox=true after unverified cleanup, source replay after restart, or a live remote sandbox falsely reported absent. N-ality separates owner, source, approval, controller state, Docker resources, time and host. Simplex and continuum deferred pending repeated host measurements; fuzzy authorization is not applicable.
