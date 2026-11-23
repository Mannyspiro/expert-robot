# Merlin Studio opt-in OpenSandbox — acceptance checkpoint (2026-11-22)

**Status: real native Studio-to-Docker and HTTP approval lifecycle passed on a disposable GitHub runner. Not merged, deployed, qualified for target host or rendered browser UI.**

## Exact provenance and evidence

- [Draft PR #210](https://github.com/Mannyspiro/expert-robot/pull/210); parent PRs #208, #207, #206 and Studio #194.
- OpenSandbox pinned Apache-2.0 source at commit 2ff37a988e4df129babaa6f07bb616394ef94086. Native Ubuntu + Docker + Python 3.11; Python image python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535.
- [Studio source/ZIP run #45099108452](https://github.com/Mannyspiro/expert-robot/actions/runs/45099108452): success. All **7/7 new Studio opt-in tests** and **9/9 inherited OpenSandbox/Z.ai tests** passed. Deterministic source-only ZIP passed manifest/hash verification and extracted offline startup, state persistence and restart smoke. [Portable ZIP/receipt artifact #14784900763](https://github.com/Mannyspiro/expert-robot/actions/runs/45099108452/artifacts/14784900763), expires Dec 7, 2026.
- [Native Docker run #45099108446](https://github.com/Mannyspiro/expert-robot/actions/runs/45099108446): success. The live controlled network canary, Docker resource/mount limits, timeout and cleanup gates passed. The **actual Studio ToolSet** (not the manual CLI) executed a script via OpenSandbox with a synthetic affirmative approval, returned stdout sentinel MERLIN_STUDIO_NATIVE_OK with source SHA-256 and real sandbox ID, then independently verified sandbox/egress container and named-volume cleanup. This Studio tool episode took **3.58 seconds** on that runner. [Native JSON/log evidence #14784403139](https://github.com/Mannyspiro/expert-robot/actions/runs/45099108446/artifacts/14784403139), expires Dec 7, 2026.
- [Inherited self-healing regression #45099108434](https://github.com/Mannyspiro/expert-robot/actions/runs/45099108434): success. The repository's generic CI workflow was canceled by concurrency; do not misreport that one as passing.

## Implementation and authority

The original run_python action retains run-specific approval and SHA-256 source check. The default is host worker mode and explicitly reports python_sandbox=false. Opt-in requires operator environment MERLIN_PYTHON_BACKEND=opensandbox and MERLIN_SANDBOX_IMAGE with immutable OCI SHA256 digest, optionally MERLIN_SANDBOX_PORT and OPEN_SANDBOX_API_KEY stored outside source/chat.

Unknown backend, invalid digest or port disables the tool instead of running code on the host. In sandbox mode the approval binds source hash, backend, image and port; changes require a new approval. The optional backend is included as a standard-library-compatible Studio module in the verified portable ZIP. Model weights, Docker, SDK and credentials are not distributed. Canonical conversation/audit/ArtifactRef behavior stays in Studio.

## Limits and next gates

1. Native ToolSet-only test used a synthetic affirmative approval; a subsequent native HTTP API test now verified real approval/denial endpoints. Rendered browser UI still needs separate acceptance.
2. The OpenSandbox SDK is synchronous and cannot hard-interrupt an in-flight execution on Studio cancellation. The server and command have separate time limits but control-plane requests may still exceed the Studio deadline.
3. No testing on intended OCI/desktop host, real-model tool selection, concurrency, target memory/speed, or broader kernel/transport isolation. Docker canary success is not a complete security certification.
4. The test Python image is digest pinned; OpenSandbox execd and egress images used upstream tags. Pin/evaluate their artifact provenance before a release.

**Ranked work:** hard cancellation during active execution and orphan cleanup; rendered browser UI acceptance; target-host native evidence and image digests; workload/cost comparison; reviewed parent PRs, explicit release approval and deployment only after those gates.

**Skeptical-scientist framing:** Hypothesis is stronger isolation without reducing approval integrity; real CI proves a narrow source-bound Docker execution and cleanup. Falsifiers are host fallback, stale approval, residual processes, unbounded execution or target-host failures. N-ality separates source, permission, host, egress, cost, persistence and UI. Simplex/continuum deferred pending calibrated performance data; fuzzy authorization not applicable.

## Additional verified native HTTP lifecycle (same experimental branch)

- [GitHub Actions run #45099445901](https://github.com/Mannyspiro/expert-robot/actions/runs/45099445901): **success**, using the same pinned OpenSandbox source and disposable Ubuntu Docker host. [Machine-readable HTTP/canary/resource evidence artifact #14784234551](https://github.com/Mannyspiro/expert-robot/actions/runs/45099445901/artifacts/14784234551); expires Dec 7, 2026.
- The actual Studio loopback HTTP application and session-token API, backed by SQLite and the canonical ArtifactRef registry, passed **five HTTP cases**: denied approval caused no execution; canceling while waiting invalidated the stale pending approval; changed script content rejected an old source-hash approval before Docker execution; normal approval executed Python in an actual sandbox and stored a matching ArtifactRef receipt; clean server restart rotated its mutation token and did not replay the prior run.
- The single approved native HTTP action took **3.73 seconds** in CI. It did not use a real LLM or cloud model and did not require user credentials.
- This is **HTTP application verification**, not a visual inspection or interaction with the rendered Studio browser page. Cancellation was intentionally exercised *before* approval, not during active in-flight SDK execution. The latter remains open.
