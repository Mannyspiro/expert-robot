# Merlin Studio in-flight OpenSandbox cancellation — acceptance checkpoint

**Status:** real in-flight cancellation and runtime cleanup demonstrated on the disposable GitHub Ubuntu/Docker runner. **Not merged or qualified on the deployment host.**

## Source, runtime, and measured evidence

- [Draft PR #212](https://github.com/Mannyspiro/expert-robot/pull/212), on top of opt-in Studio PR #210, native OpenSandbox PR #208 and earlier component PRs. Tested code head 4933bcb737d713d470720ceb5e4b925c2c638f8d.
- OpenSandbox Apache-2.0 upstream pinned at 2ff37a988e4df129babaa6f07bb616394ef94086. Disposable Ubuntu GitHub Actions with Docker bridge, a locally authenticated controller and dns+nft egress, and a digest-pinned Python runtime image.
- [GitHub Actions #45099952865](https://github.com/Mannyspiro/expert-robot/actions/runs/45099952865) **passed**: 4/4 new SDK cancellation fixture tests, 7/7 opt-in Studio approval tests, 9/9 inherited provider contract tests; deterministic portable ZIP/restart smoke passed.
- [Native Docker run #45099952655](https://github.com/Mannyspiro/expert-robot/actions/runs/45099952655) **passed**: native Docker-top observation of a real running Python script, cancellation from the actual ToolSet callback, remote kill accepted, interruption reported and main/egress containers plus named runtime volume independently absent after. Approximate observed-to-cleanup time **0.53 seconds** for this one run.
- [Extended native HTTP run #45100170367](https://github.com/Mannyspiro/expert-robot/actions/runs/45100170367) **passed**, on commit 4933bcb737d713d470720ceb5e4b925c2c638f8d. The real Studio HTTP API was used to approve a long-running script, Docker-top independently observed its process, then the HTTP cancel endpoint changed run state and the monitor requested remote termination. Managed containers and volumes were absent after ~**0.57 seconds** from the HTTP cancellation request in this one sample. The denial, pending-cancel, stale source, normal native artifact persistence and restart checks also passed. [Native JSON and server evidence #14785380597](https://github.com/Mannyspiro/expert-robot/actions/runs/45100170367/artifacts/14785380597), expires December 7, 2026.

## Mechanism and authority preservation

OpenSandbox's synchronous command stream now runs on a bounded helper thread so Studio can poll its existing cancel callback. For cancellation during active execution, the owner requests irreversible remote SandboxSync.kill(), waits for the client stream to stop, and closes its transport. A normal return still calls destroy(). A failed control-plane kill **does not** yield a false clean-cancellation result. The default host worker and explicit source-hash/backend/image/port approval binding remain unchanged.

The native test confirmed the exact Python process was running before requesting cancel, not just that a sandbox container existed. The independent Docker inspection confirms the postcondition for the tested runner; an SDK kill acknowledgement alone is not accepted as resource cleanup proof.

## Outstanding gaps and falsifiers

1. Sandbox creation, control-plane configuration, file transfer and remote controller failure can still delay cancellation while their synchronous SDK operations block. Even during active command cancellation, a prolonged unresponsive controller is not a hard real-time termination guarantee. The helper reports an error rather than success if kill is unacknowledged or the stream does not exit within its bounded grace.
2. The timing figures are single samples on GitHub's disposable Linux runner. They are not a latency SLA, OCI result, or production resource budget. Collect repeat samples and run on target host.
3. The test drives a real local HTTP server, but does not visually interact with the Studio browser UI. Browser UX, model-selected actions and full end-user credential/authorization flows require separate qualification.
4. A killed SDK client with a controller outage, crashed host, OCI reboot and orphan cleanup after unclean restart still require fault-injection recovery testing and an operator-owned reaper.
5. The upstream egress and execd image tags, supply-chain provenance and target runtime security must be pinned/audited independently before production release.

## Next ranked production work

First, design and test crash-safe orphan reconciliation on host restart (using exact sandbox ownership labels and owner/lease policy); second, verify bounded controller creation and request cancellation under fault injection; third, run on intended OCI/desktop host with pinned image digests and repeated resource/latency samples; fourth, visual Studio UI and model-enabled agent acceptance; fifth, review nested PRs and approve any production release explicitly.

Scientific distinction: measured cancellation is a narrow Docker and HTTP experiment, not a proof of every interruption mode. N-ality records independent run, authorization, host, process, network, state and resource axes; simplex/continuum deferred until repeated host-side data, fuzzy approval never applicable.
