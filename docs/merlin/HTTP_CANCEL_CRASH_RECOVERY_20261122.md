# Merlin Studio HTTP cancellation, crash recovery and pinned runtime
**Checkpoint date:** November 22, 2026 (Arizona) / November 23, 2026 (UTC).

**Status:** native acceptance succeeded on a GitHub-hosted, ephemeral Linux/Docker runner. All changes remain **draft**; no target OCI host release, real model inference or rendered-browser approval was exercised.

## Exact identities

- Source: [draft PR #213](https://github.com/Mannyspiro/expert-robot/pull/213), based on #212 -> #210 -> #208/#207 -> #206.
- OpenSandbox reviewed Apache-2.0 source: commit 2ff37a988e4df129babaa6f07bb616394ef94086.
- Python OCI image: python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
- OpenSandbox execd OCI image: opensandbox/execd@sha256:6cf7dba2f21f0b536e100563d841ac58a9f31c2b0a081b7ac76796a24d6f47e2
- OpenSandbox egress OCI image: opensandbox/egress@sha256:db7345d567b0970f384b8e3fa7a93a71b7f43d4b16bb2009de34096e9a87b3b5
- Registry digest readback: [CI run 45099952655](https://github.com/Mannyspiro/expert-robot/actions/runs/45099952655), job 137448252483.
- Digest-pinned source acceptance: [CI run 45100308746](https://github.com/Mannyspiro/expert-robot/actions/runs/45100308746), **success**, tested source commit a1aae0925f3e81ed15e0240dba8e5a39e5ee092b. [Native evidence artifact 14784169764](https://github.com/Mannyspiro/expert-robot/actions/runs/45100308746/artifacts/14784169764), expires December 7, 2026.

## Observed results on the pinned-runtime source

1. Positive control: ordinary Docker bridge Python reached a controlled local HTTP canary. OpenSandbox denied the same destination with dns+nft. Live Docker inspection confirmed 512 MiB memory, one CPU, 64 PIDs, non-privileged main container, only its ID-bound managed runtime volume, no arbitrary host bind, and final cleanup. Full native acceptance completed in 27.8 seconds on this specific runner.
2. Studio HTTP approval/denial test passed: declined and pending-cancelled actions did not execute, changed source after pending approval was rejected, real approved script produced the expected output and canonical artifact identity, and graceful restart did not replay a completed action. The normal HTTP-approved Python script elapsed 3.62 seconds on this runner.
3. A running long-lived script was independently observed using Docker top, then interrupted using Studio ToolSet. The test measured 0.42 seconds between process observation/cancellation and independent resource cleanup.
4. New active HTTP cancellation test independently observed a running 90-second sleep script, sent POST /api/runs/:id/cancel through the Studio server, and confirmed the worker stopped, no completed tool result was logged, and the main container, egress container and managed volume disappeared. One observed interval: 0.38 seconds. This is a single sample, not a guaranteed latency.
5. Separate source-only real-process crash regression deliberately SIGKILLed its own temporary Studio server while an approval was pending. Reopening the same saved state marked the run interrupted, rejected old approval and session tokens, and executed no unapproved script.
6. [Studio portable workflow 45100308710](https://github.com/Mannyspiro/expert-robot/actions/runs/45100308710) passed 7 opt-in tests, 4 cancellation fixture tests, 9 OpenSandbox/Z.ai tests, a hash-verified deterministic ZIP, extracted startup/restart and the real subprocess crash test. Generic repository CI cancelled by concurrency, not counted as success.

## Authority and limits

- Approval binds script SHA-256, chosen backend, OCI image and port; invalid configuration disables Python rather than silently using the host.
- A deliberately stopped OpenSandbox controller **during** an active execution and reliable recovery of any resulting orphan remain unverified. A maximum sandbox lifecycle is not independent cleanup proof under a controller outage.
- HTTP fixture authorization is not rendered browser/user-interaction acceptance. There was no real local-model tool selection or real OCI/desktop deployment.
- Digest pinning identifies artifacts, not cryptographic signing, SBOM verification or a comprehensive security audit. No release, automatic merge, source promotion, cloud spend or weights training occurred.

## Next ranked work

1. Fail-closed controller outage/restart experiment while an approved Python script is actively executing; independently verify or falsify orphan cleanup and state recovery.
2. Test rendered Studio UI consent, cancellation and status honesty with a real local browser, then model-selected tool flow.
3. Reproduce the pinned native acceptance on the target OCI/desktop host; verify supported OS/ABI/resource budgets.
4. Measure replicated task correctness and latency/RAM/CPU against the original host worker before choosing a resource optimization.
5. Review stacked draft PRs and require explicit release approval before merge or deployment.

## Skeptical scientist framing

Hypothesis: Studio HTTP cancellation can stop a running approved sandbox without source/approval mismatch or resource leakage. Predicted observable: actual Docker process before cancellation, no completed tool result, independent full cleanup within 15 seconds. Observation: one pinned runner passed. Alternative: controller or SDK failure can leave an orphan. Falsifier: changed script executes under old approval; a running script outlives cancellation undetected; any main/egress/volume remains. N-ality applied to source, authority, execution phase, network isolation, persistence, host class and resource identity; simplex and continuum deferred pending replicated measurements; fuzzy is not applicable to strict Boolean permission or integrity gates.
