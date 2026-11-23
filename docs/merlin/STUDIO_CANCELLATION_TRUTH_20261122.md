# Merlin Studio cancellation truth and real controller recovery

Date: 2026-11-22 (UTC 2026-11-23)
Status: Native Linux/Docker candidate verified. Draft PR #216 is **not merged, released or deployed**.

## Defect and exact change

Previously Studio accepted HTTP Cancel by marking the run terminal "cancelled", even while a remote OpenSandbox process could still be running. A failed controller deletion could therefore produce a false safe-stop report. The independent owner journal from PR #215 already preserved remote cleanup intentions but did not distinguish a stop request from its confirmed completion.

The present change introduces a nonterminal **cancelling** status in the original SQLite Studio store. Cancel revokes a pending approval and writes a one-time cancel_requested event, but only the worker can finalize a run. The completion transaction tests the durable sandbox pending-intent table: if any cleanup for the run remains unverified, it marks the run **failed** with explicit cleanup warning and retains the pending row. Studio disables further sandbox work until owner reconciliation succeeds. The browser displays "Stopping — verifying cleanup…" and disables duplicate Stop presses. Restart transitions an unfinished cancelling run to interrupted and never replays it.

No change to the optional backend choice, per-script human approval, source hash, immutable image or host fallback policy. No direct automatic deployment or tool authority was granted.

## Real, source-scoped evidence

- [Draft PR #216](https://github.com/Mannyspiro/expert-robot/pull/216), source commit df052c15a35d88f4279f66326fc8280f88745cd3.
- [Native OpenSandbox Docker GitHub Action 45102079506](https://github.com/Mannyspiro/expert-robot/actions/runs/45102079506), job 137454984518, **success**. [Native evidence artifact 14785882794](https://github.com/Mannyspiro/expert-robot/actions/runs/45102079506/artifacts/14785882794), expires 2026-12-07.
- A test first approved a deliberately long Python script, witnessed its running Docker process, terminated only the disposable Studio process, and then **SIGSTOPed the disposable OpenSandbox controller**. Restarted Studio served its local API but reported Python sandbox disabled, one durable pending intent, and controller cleanup not verified. An old approval was rejected. After SIGCONT of the same controller, Studio restarted and removed the exact owned orphan, cleared the intent, did not replay the script, and restored the sandbox tool.
- The same native workflow repeated controlled network denial, independent Docker resource inspection, host mount rejection, source-bound HTTP approval, active cancellation and cleanup. The real HTTP active-cancel test reported approximately **0.41 seconds** for termination/cleanup after observing the process. This is one CI timing observation, not a latency benchmark.
- [Studio portable + cancellation gate 45102079487](https://github.com/Mannyspiro/expert-robot/actions/runs/45102079487), **success**; eight new cancellation-truth tests plus 8 Studio opt-in, 11 owner-recovery, 4 SDK cancellation and 9 optional-provider tests passed. A portable ZIP and extracted offline restart passed. [ZIP and receipt artifact 14786061593](https://github.com/Mannyspiro/expert-robot/actions/runs/45102079487/artifacts/14786061593), expires 2026-12-07.
- [Experimental self-healing CI 45102079525](https://github.com/Mannyspiro/expert-robot/actions/runs/45102079525), **success**. The separate generic CI job was canceled by existing concurrency rules; it is **not** counted as a full generic CI pass.

## Known limits

The result is confined to a GitHub-hosted Linux Docker runner using source-pinned OpenSandbox and immutable OCI images. It does not independently qualify the user's OCI server or desktop OS, interactive rendered browser clicks, security of arbitrary hostile workload or all network paths, or real model-selected tool calls. Startup reconciliation is owner-scoped and requires the controller's listings to correctly report ownership; untagged older sandboxes are not recoverable by this mechanism. When controller cleanup is unverified, Merlin reports an explicit failure and blocks further sandbox Python rather than claiming success. Model inference, UI accessibility and host deployment are separate gates.

## Ranked continuation

1. Exercise actual rendered Studio browser workflows (approve, deny, stop, visible provisional stopping and persisted Activity) with reproducible Playwright receipts.
2. Reproduce controller outage/restart on the intended OCI host with immutable source/runtime identities and independent Docker inspection. Do not report the CI host as equivalent.
3. Test model-selected code execution with a locally controlled model fixture and per-action approval to end-to-end event/artifact evidence.
4. Review resource/latency distributions and any controller policy drift across multiple independent runs, then update budgets.
5. Reconcile the draft PR dependency graph with original Studio PR #194 and GitLab release procedures; require explicit owner review and release authorization before merge/deploy.

## Skeptical-scientist scope

Observation: a real controller outage left remote work live but did not allow new sandbox execution; eventual cleanup was confirmed on controller restoration. Competing mechanism: a controller could return stale or incorrect owner/status records, or lose access to a sandbox during a different outage. Falsifier: any old approval replay, unauthorized host fallback, false terminal "cancelled" with pending owner intent, or owner-mismatched termination. N-ality kept approval, source, controller availability, cleanup, time and target host as separate axes. Simplex and continuum remain deferred until repeated performance/cost samples exist; fuzzy scoring never substitutes for Boolean authorization.
