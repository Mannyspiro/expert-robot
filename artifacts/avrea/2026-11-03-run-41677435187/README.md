# Avrea runner evidence — CI run 41677435187

- Repository: Mannyspiro/expert-robot
- PR: #67 (draft)
- Workflow: CI, run 1182
- Job: build-and-smoke, ID 126061727081
- Checked-out merge commit: 9d63bec (merge of 731ecefb8fd6ef0533059ca2253899c55f859847 into b57bd0a1b92882e6cdc14d97e5b9208afb831a63)
- Runner version: 2.338.2
- Runner: avrea-exe-01a1a24d3e8771b5b710d9ee3452ea3c
- Machine: vrm-01a1a24d414a7db5846655e61f187e99
- Architecture: x86_64; AMD EPYC 4585PX; 8 vCPUs; KVM
- Memory at probe: 29 GiB total, 28 GiB available; 3 GiB swap
- Build parallelism: 8 workers
- Toolchain: GNU 13.3.0; CMake/Ninja; SQLite 3.45.1

## Results
- Build: passed.
- CTest: 33/33 passed.
- Voice contracts: 6/6 passed.
- Engineering tests: 14/14 passed, including 4 new CPU-fabric regression tests:
  - development/held-out seed disjointness,
  - loader receives exact verified snapshot,
  - randomized paired differences and held-out split,
  - transient artifact cap enforced at registration and activation.
- Research/API tests: 26/26 passed.
- Policy, known-failure, benchmark progression, formal dependency, CACE bridge, collar, and independent smoke checks: passed.
- NousCoder inference job: skipped; this does not qualify model inference.
- The run checked the merge of commit 731ecef, which includes the catalog corrections, paired evaluator, graph explorer, and corrected CPU-fabric test imports. It is not a browser automation test of the HUD.

Complete raw log: `avrea-ci-run-41677435187-job-126061727081.log`.
