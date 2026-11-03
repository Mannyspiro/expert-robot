# Avrea runner evidence — CI run 41675662882

- Repository: Mannyspiro/expert-robot
- Pull request: #67 (PR merge ref was checked out)
- Workflow: CI, run number 1166
- Job: build-and-smoke (job ID 126055582609)
- Runner: avrea-exe-01a1a2439a8c75f6972aaba5f122b75c
- Machine: vrm-01a1a2439d3d7d128145e0e3acb8e1f7
- Runner version: 2.338.2
- Architecture: x86_64; AMD EPYC 4585PX; 8 vCPUs; KVM
- Memory: 29 GiB total, 28 GiB available at probe; 3 GiB swap
- Build workers: 8
- Compiler: GNU 13.3.0; CMake/Ninja; SQLite 3.45.1
- Outcome: C++ build and all 33 CTest tests passed. Guardrail checks shown in the log passed. Research Python unittest suite failed: 26 tests run, 1 failure.
- Failure: `test_telemetry_ingest_and_source_separation`; expected runtime source count 1 but observed 23. This is a test isolation defect caused by sharing the class-level EventStore across tests while HTTP boundary telemetry records runtime events.
- NousCoder inference job was skipped. No model inference qualification is established.
- This run is from the PR merge ref at merge commit `feb641fdcf21410f3442e952675f15677423ed5e`, which includes commit `f11622b1c337d2f37c51d26d8bd388403c66d7e5`. It does not prove that subsequent commits are tested.

The complete raw job log is stored alongside this report as `avrea-ci-run-41675662882-job-126055582609.log`.
