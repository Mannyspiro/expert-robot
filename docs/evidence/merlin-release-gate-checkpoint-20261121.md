# Merlin release verification checkpoint — 2026-11-21

This is a **non-promoting** engineering checkpoint. It does not supersede the canonical master plan.

## Source and observed results
- Release evidence checker branch: `merlin/release-gate-evidence-20261121`.
- Byte verification, bounded reads (16 MiB), path containment, symlink rejection, consistent reported source commits, and fail-closed missing-evidence behavior added.
- Independent local Python 3.13.5 test execution: **11/11 passed**; `compileall` succeeded.
- Empty manifest CLI returned exit code **1** (expected).
- CI run 44963788433 on commit `f8774d8713a338e34053889f05d07544d6dde70c` reported **failure**. Job 137028154109 failed. Root cause **unknown** because GitHub connector did not provide usable step logs.
- Earlier self-healing workflow 44963258585 failed and its rerun failed. Do not treat the failures as fixed.
- Release checker verifies **bytes and locators only**, not evidence truth, execution independence, native model inference, user access, or release authorization.

## Ranked next evidence gates
1. Obtain exact GitHub Actions job-step failure diagnostics and reproduce the CI failure on its actual runner/environment. Preserve failing logs and source identity.
2. Reconcile native browser retained state under the existing recovery/approval protocol, then run real Unix socket peer/ownership tests on the intended host.
3. Run Studio's full 111-test suite with Python >=3.10 on the exact source package; test the archive inspector on the real archive.
4. Bind a separately supplied local model and demonstrate one real request, independent task-specific evaluation, evidence persistence, restart, and readback.
5. Validate offline ZIP extraction, launch, UI access, controlled online tools, and rollback on a clean target host.
6. Obtain the required review and explicit release decision only after acceptance gates pass. No automatic merge or deployment.

## Reasoning lenses
- Simplex: not applicable to the Boolean release gates; authorization cannot be averaged.
- n-ality: applied as independent dimensions of integrity, runtime, model, browser, persistence, and rollback.
- Continuum: not applicable to discrete acceptance; performance thresholds remain separate future measurements.
- Fuzzy: not applicable to integrity or authorization; uncertain evidence is not a partial pass.

## Contradictions and limits
A passing local unit suite and a failing GitHub Actions job can coexist. The failure may be environment-specific, source-dependent, or due to a test defect; without job logs none is established. Do not change the acceptance thresholds to make CI green.
