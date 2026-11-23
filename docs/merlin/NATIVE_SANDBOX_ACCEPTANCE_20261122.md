# Merlin native OpenSandbox acceptance — 2026-11-22 / UTC 2026-11-23

**Decision: native isolated execution demonstrated on ephemeral GitHub Actions Linux/Docker only.**
This is evidence for a candidate backend, not a production-host or general container-security certification and not approval to merge.

## Exact evidence and prerequisites

- Source: Merlin [draft PR #208](https://github.com/Mannyspiro/expert-robot/pull/208), based on draft #207 → #206 → #194.
- OpenSandbox: Apache-2.0 source pinned to commit `2ff37a988e4df129babaa6f07bb616394ef94086`.
- [Complete passing GitHub Actions run #45098496829](https://github.com/Mannyspiro/expert-robot/actions/runs/45098496829), exact head `51094340ffad4df1a31f0eda0ecfad400756003c`.
- [Machine-readable JSON and redacted server-log artifact #14783859678](https://github.com/Mannyspiro/expert-robot/actions/runs/45098496829/artifacts/14783859678), expires December 7, 2026.
- CI environment: GitHub-hosted Ubuntu, Docker bridge, local OpenSandbox API, ephemeral API key, Python 3.11 client, `dns+nft` egress sidecar, image `python@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535`. The execd/egress image *tags* were v1.1.0/v1.1.7 and were not separately immutably pinned in this run.

## Observed tests (native, not mocked)

1. An ordinary Docker bridge container reached a live HTTP canary on the runner's bridge gateway. An OpenSandbox container sharing its protected sidecar namespace could **not** reach the same canary; the Python caller reported `URLError` and the canary observed no additional request.
2. Docker inspect confirmed main sandbox `Memory=536870912` bytes (512 MiB), `NanoCpus=1000000000` (one CPU), `PidsLimit=64`, `Privileged=false`, dropped `NET_ADMIN`, `NET_RAW`, `SYS_ADMIN`, and `SecurityOpt` containing `no-new-privileges=true`.
3. Docker mount inspection confirmed **only** the exact named `opensandbox-runtime-<sandbox ID>` volume at `/opt/opensandbox` (RW); no arbitrary host bind source. The main container's network namespace was `container:<egress-sidecar ID>`. The native test separately rejected host bind, wrong owner, wrong type, and extra/incorrect runtime mounts in **5/5 negative unit tests**.
4. A 120-second sleep with a two-second command timeout failed in approximately 5.1 seconds including startup and cleanup; sandbox main containers, egress sidecars and managed runtime volumes were absent after termination. The full latest acceptance ran in **22.81 seconds** (not a performance benchmark).

## Real defects found and repaired, without relaxing acceptance

| CI run | Defect family | Repair |
| --- | --- | --- |
| [45097913531](https://github.com/Mannyspiro/expert-robot/actions/runs/45097913531) | Server requires ≥60-second sandbox lifecycle; client requested 45 seconds | Set lifecycle to 60 seconds and add fixture assertion |
| [45098033912](https://github.com/Mannyspiro/expert-robot/actions/runs/45098033912) | SDK expects permission digits `600`, not integer representation of `0o600` | Use `mode=600` and test the request contract |
| [45098161549](https://github.com/Mannyspiro/expert-robot/actions/runs/45098161549) | Pinned command API requires string, not argv list | Use fixed `python -I -B /tmp/merlin_approved.py` |
| [45098274949](https://github.com/Mannyspiro/expert-robot/actions/runs/45098274949) | Test incorrectly classified OpenSandbox's required named runtime volume as host bind | Permit only the exact ID-bound runtime named volume, add five negative tests and verify cleanup |

None of these failed tests was reclassified as passing. Both the real-traffic negative test and live resource constraints remained mandatory. The test runner's report remains an experimental receipt: there is no independent audit of Docker, kernel, gVisor/Kata, sidecar image dependencies, container breakout behavior, or malicious workload resistance.

## Next ranked production slice

**First:** wire the now-tested runner to Merlin Studio as an explicit opt-in alternative, preserving script-byte approval, no host fallback, artifact identity, bounded output and old default behavior; test real cancellation and restart separately. **Second:** reproduce the native acceptance on the actual approved OCI/desktop host with the same source and image identities. **Third:** audit supply chain and egress image digests; enforce a pinned backend configuration at release time. **Fourth:** evaluate Graft tool candidates only inside that boundary with independent permission, credential and evidence checks. **Fifth:** reconcile review/merge/deployment gates across parent PRs before claiming production release.

### Skeptical-scientist record

Question: does container-backed execution reduce host-side risk while retaining usable code execution? Baseline: original Studio worker is a host Python subprocess and explicitly not an OS sandbox. Observation: the representative native Docker experiments above passed. Competing explanation/limit: enforcing egress to one canary and inspecting one container does **not** prove all network or kernel boundaries. Falsifier: direct/IPv6/alternate-protocol escape, secret leakage, unauthorized host bind, residual process, invalid approval, failed cancellation or regression on the target host. N-ality axes (source, memory, network, authority, identity, persistence, host) kept distinct; simplex/continuum deferred until comparable samples; fuzzy authorization not applicable.
