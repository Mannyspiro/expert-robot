# Railway Free Preflight

This repository can offload fail-fast build/test work to Railway's free
`ssh railway.new` VM without consuming an Avrea runner.

## Workflow

Run **Railway Free Preflight** from GitHub Actions.

Inputs:

- `ref`: branch, tag, or commit to test.
- `mode`: `cheap`, `targeted`, or `full`.

The workflow uses a GitHub-hosted `ubuntu-latest` runner only to:

1. check out the requested ref,
2. package the source tree,
3. authenticate to `railway.new`,
4. copy the source bundle to the Railway VM,
5. relay logs/evidence back to GitHub.

Compilation and tests run on the Railway VM.

## Credential boundary

The repository secret is:

```text
RAILWAY_SSH_PRIVATE_KEY
```

The private key is written only to the GitHub runner's temporary directory with
mode 600 and is deleted in an `always()` cleanup step.

The private key is **not copied into the Railway VM**.

The VM receives only a source archive. This means GitHub repository credentials
are not delegated to the free VM.

## Resource policy

The Railway free VM is treated as an advisory preflight worker:

```text
Railway preflight failure -> stop/escalate for debugging
Railway preflight pass    -> candidate may proceed to repository CI
Railway pass              != qualification or promotion
```

The workflow forces one build worker because the anonymous/free VM is currently
2 vCPU / 2 GB RAM.

The persistent CMake build directory lives at:

```text
/app/.expert-robot-cache/build-preflight
```

This allows repeated runs against the same Railway VM to reuse CMake/Ninja
state while replacing the source checkout cleanly.

## Evidence

When available, the workflow downloads:

```text
preflight-summary.json
```

and uploads it as a GitHub Actions artifact named:

```text
railway-preflight-<run-id>
```

Evidence is retained for 14 days.

## Security notes

- Railway provisioning JSON is filtered from Actions output so one-time claim
  URLs are not written to future workflow logs.
- The previously exposed private key must remain revoked.
- The current secret should contain only the newly rotated key.
- This workflow grants no promotion authority.


## Runner-repository bridge

The same SSH key can also be used as a GitHub deploy key for the repository
that owns additional Actions runners.

The workflow defaults to:

```text
git@github.com:morganaspim/Cace-app.git
```

and exposes this as the `runner_repo_ssh` workflow input.

When `discover_runner_repo = true`, the GitHub dispatcher:

1. loads the private key into a local `ssh-agent`,
2. connects to Railway with SSH agent forwarding (`ssh -A`),
3. performs a read-only `git ls-remote` against the runner repository,
4. shallow-clones it temporarily on Railway,
5. prints only workflow filenames and referenced `runs-on:` labels,
6. deletes the temporary clone.

The private key itself is never copied onto Railway for this discovery path.

This does **not** automatically register those runners to Expert Robot. GitHub
self-hosted runners remain scoped according to the repository/organization
where they were registered. The discovery step tells us what runner labels and
existing workflows are available so a later bridge can hand off work through
that repository without weakening the authority model.
