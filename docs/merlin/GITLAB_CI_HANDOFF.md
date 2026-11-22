# Merlin GitLab CI execution handoff

GitHub is authoritative: `Mannyspiro/expert-robot`. GitLab is a disposable
build environment, **not** a source-of-truth mirror. No deployment or merge is
performed by this workflow.

## One-time GitLab setup

1. Create a new project named `merlin-production-ci` in the intended GitLab
   namespace (private recommended; public job logs can disclose diagnostics).
2. Create its root `.gitlab-ci.yml` by copying the complete contents of
   `ci/gitlab-merlin-exact-revision.yml` from the reviewed GitHub commit.
3. Verify GitLab CI/CD runners are enabled, the trial's available compute
   minutes, and that the project permits manual web pipelines.
4. Do not configure GitHub write credentials, OCI SSH keys, model secrets,
   or automatic deployment in this CI project.

## Run a reproducible verification

1. Record the full 40-character GitHub commit SHA to test. Use the latest
   reviewed commit from `merlin/release-gate-evidence-20261121`, not a moving
   branch name.
2. GitLab > Build > Pipelines > New pipeline: ref `main`, variable
   `MERLIN_GITHUB_SHA=<reviewed-40-character-sha>`.
3. Start the manual `merlin-exact-revision` job.
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

The CI job is manual-only, capped at 60 minutes, and retains evidence 14 days.
Do not put credentials or private user context into logs or artifacts.
