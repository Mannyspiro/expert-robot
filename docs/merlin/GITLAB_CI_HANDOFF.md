# Merlin GitLab CI execution handoff

GitHub is authoritative: `Mannyspiro/expert-robot`. GitLab is a disposable
build environment, **not** a source-of-truth mirror. No deployment or merge is
performed by this workflow.

## One-time GitLab setup

1. Use the existing private GitLab project `spiro-investments-group/merlin-project-ci` (ID `89293141`).
2. Its root `.gitlab-ci.yml` now has a validated `spec:inputs.github_sha` field, a frozen reviewed default and an API-only workflow. Direct pipeline-variable overrides remain restricted; the typed input is the permitted route. The GitHub copy is `ci/gitlab-merlin-exact-revision.yml` and should be kept synchronized.
3. GitLab runners are available. API-sourced pipelines have run; confirm remaining compute budget before extended tests.
4. Do not configure GitHub write credentials, OCI SSH keys, model secrets,
   or automatic deployment in this CI project.

## Run a reproducible verification

1. Record an exact reviewed, reachable 40-character lowercase GitHub commit. Verify its source branch and desired tests; do not use a moving branch name.
2. Start a pipeline via the GitLab API on `main` with `inputs: {"github_sha": "<exact 40-character commit>"}`. The input schema rejects non-SHA strings; CI also validates the commit format and detached checkout.
3. Review the `merlin-exact-revision` job, whose runner installs `libsqlite3-dev` in addition to the C++/Python build tools and executes the pinned GitHub source. The frozen default is only for deliberate baseline runs.
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

## Measured results and current acceptance scope (21 November 2026)

- Recovery-graph repair at `fd0560e2453817328fe23f2729bb056b61ed2e4e`: GitLab pipeline [3098840706](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3098840706) passed.
- Durable six-stage scientific cycle at `3cf9754a4fd37df13d90f6b46cbf2f24496888c4`: pipeline [3098865351](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3098865351) passed.
- Hardened receipt/readback and append-only plan update at `28f981a7d31dc72b9244711904ff0beb409ec35c`: pipeline [3098868686](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3098868686) passed.
- Exact registry ArtifactRef/immutable-version integration at `a8d78baa3d50a8b69490214ad3384d8079e9ded3`: pipeline [3098871583](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3098871583) passed.
- Reproducible actual local-registry research fixture at `8a51ebb113ce023200af0fac892637f10d576aab`: pipeline [3098873975](https://gitlab.com/spiro-investments-group/merlin-project-ci/-/pipelines/3098873975) passed.
- Separate Studio native HTTP/transport/portable packaging and extracted startup source is being validated; do not report completion until the exact current pipeline is inspected.

A full pipeline runs `scripts/run_merlin_offline_ci.sh`: the Merlin loop, scientific, source preflight, native C++/CTest, smoke checks, portable Studio HTTP/model boundary tests, package build/manifest verification, and the extracted offline/restart acceptance on revisions containing those steps. The success of a prior commit is **not** success of later changes. The Studio ZIP includes no model weights, Python runtime or inference engine. Native protocol health is not model inference.

### Evidence review and guardrails

Inspect each job's checked-out `HEAD` and `PASS: <SHA>` marker, then collect `merlin-preflight.json` and `merlin-evidence/` artifacts. A green job establishes only the checks run on that source. Preserve failed/null logs, missing evidence, timeout and blocked approvals. Never infer production deployment, research truth, code promotion, off-host recovery, desktop automation or real inference from synthetic tests. New scopes require their own acceptance runs. External model spending is $0, and the accepted runner path excludes Avrea and ChatGPT account/site access.

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
