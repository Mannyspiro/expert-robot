# Merlin GitLab CI execution handoff

GitHub is authoritative: `Mannyspiro/expert-robot`. GitLab is a disposable
build environment, **not** a source-of-truth mirror. No deployment or merge is
performed by this workflow.

## One-time GitLab setup

1. Use the existing private GitLab project `spiro-investments-group/merlin-project-ci` (ID `89293141`).
2. Its root `.gitlab-ci.yml` is installed and pins a reviewed GitHub SHA. The project restricts pipeline variable overrides, so update that SHA in a reviewed CI commit for each run.
3. GitLab runners are available. API-sourced pipelines have run; confirm remaining compute budget before extended tests.
4. Do not configure GitHub write credentials, OCI SSH keys, model secrets,
   or automatic deployment in this CI project.

## Run a reproducible verification

1. Record the full 40-character GitHub commit SHA to test. Use the latest
   reviewed commit from `merlin/release-gate-evidence-20261121`, not a moving
   branch name.
2. Update the pinned `MERLIN_GITHUB_SHA` in the GitLab `.gitlab-ci.yml` through a reviewed commit.
3. Start an API-sourced pipeline on `main`; its `merlin-exact-revision` job runs automatically.
4. Inspect the job exit code and download `merlin-preflight.json` and
   `merlin-evidence/` artifacts. Keep the exact commit and pipeline URL.
5. On failure, inspect the named failing log and reproduce the failure against
   the same SHA before changing source. Never interpret skipped tests as pass.

## Release acceptance

A green pipeline is necessary but insufficient for a production release.
Require independent review of evidence, OCI service startup, Studio API/UI
interaction, persisted state after restart, permission boundaries, and a clean
offline ZIP extraction/startup on a supported target host. GitLab's Ubuntu
runner does not prove OCI ARM or end-user offline compatibility.

## Failure routing

- No GitLab project: create the dedicated project; do not repurpose an unrelated
  repository or overwrite its code.
- GitHub DNS unavailable in runner: stop and preserve the network failure.
- Wrong SHA or dirty checkout: stop; do not silently select another revision.
- Missing packages or exhausted CI minutes: stop; adjust within approved budget.
- OCI inaccessible: keep the release blocked, even if GitLab CI is green.

The CI job is API-triggered, capped at 60 minutes, and retains evidence 14 days.
Do not put credentials or private user context into logs or artifacts.

## Measured checkpoints and current repair loop

- Pipeline 3098801750: failed at CMake configuration; the original log was retained as a job artifact but not printed in the job trace.
- Pipeline 3098809615: failed at CMake configuration with observed error `Could NOT find SQLite3 (missing: SQLite3_INCLUDE_DIR SQLite3_LIBRARY)`.
- Repair: install `libsqlite3-dev` in the GitLab Ubuntu image. Pipeline 3098815226 is the next verification run; its result must be checked before marking repair complete.
- Source `a16ffa65b3c0e40a14839833bc2db0347f295200`: deterministic `next_steps()` and `handoff()` for bounded loops, plus regression tests. These are scheduling calculations, not automatic execution or durable persistence.

## Ranked continuation, with acceptance gates

1. **CI feedback loop:** inspect the latest failed step, identify a minimal reproducer, fix root cause without skipping tests, pin the new source SHA, rerun, and preserve both failed and passing evidence. Stop at runner quota or permission limits.
2. **Durable loop handoff:** connect the coordinator's deterministic next-step output to the existing canonical ledger. Verify crash/restart restoration, parent/dependency ordering, explicit retry budgets, and no unauthorized execution.
3. **Research/reframing loop:** for failed work, record observed evidence, original problem invariants, bounded analogue/reframe, discriminating test, and translated-back result. Require a real passing original acceptance test before closing.
4. **Production vertical slice:** start the local model and Studio webserver, complete one research task with evidence, resume after restart, and inspect UI plus permission boundaries on the intended OCI host.
5. **Portable release:** extract ZIP on a clean supported offline host, launch server, exercise local chat and tools, verify hashes and rollback. Require human review before merge, deployment, or release promotion.

A task is not complete because a source file was committed. Each iteration records the exact revision, test result, remaining unknowns, and the next eligible task; failures remain visible. The loop stops on exhausted budget, blocked authorization, missing independent evidence, or explicit user stop.
