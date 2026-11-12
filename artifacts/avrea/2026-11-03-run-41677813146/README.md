# Avrea runner evidence — CI run 41677813146

- Repository: Mannyspiro/expert-robot
- PR: #67 (draft)
- Workflow: CI, run 1186
- Job: build-and-smoke, ID 126063089202
- Checked-out merge commit: 72e646c (merge of 39065a2f7cb098f3e5d6c7145c4eef49390f31ed into b57bd0a1b92882e6cdc14d97e5b9208afb831a63)
- Runner version: 2.338.2
- Runner: avrea-exe-01a1a24f4f45764490f350634c08031b
- Machine: vrm-01a1a24f528c7a4b82f5a37d514c491b
- Architecture: x86_64; AMD EPYC 4585PX; 8 vCPUs; KVM
- Memory at probe: 29 GiB total, 28 GiB available; 3 GiB swap
- Build parallelism: 8 workers
- Toolchain: GNU 13.3.0; CMake/Ninja; SQLite 3.45.1

## Results
- Build: passed.
- CTest: 33/33 passed.
- Voice contracts: 6/6 passed.
- Engineering tests: 15/15 passed, including five CPU-fabric regressions:
  - development/held-out seed disjointness,
  - loader receives exact verified snapshot,
  - randomized paired differences and held-out split,
  - transient cap enforced at registration,
  - activation rechecks the cap after the artifact changes post-registration.
- Research/API tests: 26/26 passed.
- Policy, known-failure, benchmark progression, formal dependency, CACE bridge, collar, and independent smoke checks: passed.
- NousCoder inference job: skipped; this does not qualify model inference.

Complete raw log: `avrea-ci-run-41677813146-job-126063089202.log`.
