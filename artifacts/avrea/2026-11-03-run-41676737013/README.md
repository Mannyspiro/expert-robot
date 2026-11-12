# Avrea runner evidence — CI run 41676737013

- Repository: Mannyspiro/expert-robot
- Pull request: #67 (draft)
- Workflow: CI, run number 1175
- Job: build-and-smoke (job ID 126059272613)
- Checked-out merge commit: 73c8ee6 (merge of 5385380aa95ffe2cf0ff99bd61f2bd7112f65e98 into b57bd0a1b92882e6cdc14d97e5b9208afb831a63)
- Runner version: 2.338.2
- Runner: avrea-exe-01a1a24967b0716e8bf7c19246743969
- Machine: vrm-01a1a2496b897d8a99f7fca4d5bbd265
- Architecture: x86_64; AMD EPYC 4585PX; 8 vCPUs; KVM
- Memory at probe: 29 GiB total, 28 GiB available; 3 GiB swap
- Parallel build workers: 8
- Compiler/build: GNU 13.3.0, CMake/Ninja, SQLite 3.45.1

## Results
- C++ build: passed.
- CTest: 33/33 passed.
- Policy, known-failure, benchmark progression, formal dependency, CACE return bridge, collar, Hermes/voice integration checks: passed.
- Voice contract tests: 6 passed.
- Engineering geometry/netlist tests: 10 passed.
- Research/API tests: 26 passed, 0 failures.
- Independent smoke tests: passed.
- NousCoder inference job: skipped. This run does not qualify NousCoder inference or any model route.

The earlier telemetry count failure (runtime count 23 vs expected 1) was corrected by giving the test an isolated EventStore. This CI run verifies that correction.

**Scope limitation:** This run checked merge commit 73c8ee6, which contains commit 5385380. It predates subsequent commits adding direct graph-neighbor navigation and the engineering CPU-fabric regression tests. Therefore it does not validate the exact current branch head or those newly added regression tests.

Complete raw log: `avrea-ci-run-41676737013-job-126059272613.log`.
