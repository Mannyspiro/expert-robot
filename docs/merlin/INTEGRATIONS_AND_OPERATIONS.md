# Merlin Integration and Operations Guide

**Status date:** 2026-11-04  
**Primary repository:** Mannyspiro/expert-robot (private; default branch main)

## 1. Mission and authority model

Merlin is the central research, engineering, and project-orchestration layer. It discovers and organizes work, maintains the research atlas and hypothesis ledger, routes bounded tasks, and records evidence. It is not itself proof that a claim is true or permission to deploy.

- **Merlin:** project registry, archive intake, knowledge graph, ideonomy, research plans, engineering IR, XMG coordinate/frame model, task planning and evidence index.
- **Expert Robot:** execution gateway and agent runtime; repository operations, CI/job orchestration, bounded local tools, research workers and artifact handling.
- **Hermes:** routing and coordination between Merlin, qualified workers and CACE contracts.
- **Avrea:** ephemeral GitHub Actions compute, CI acceleration, job logs/artifacts and runner observability.
- **CACE:** formal and engineering verification, typed contracts, qualification gates and evidence/hash checks.
- **MCFC:** virtual compute/worker-fabric abstraction; it is not proof that a particular remote runner is provisioned.
- **GitHub:** durable source-control record: branches, commits, PRs, reviews, workflow runs, artifacts and releases.
- **Base44:** app/backend and integration platform for Merlin/CACE-facing dashboards or operational interfaces.
- **Vercel / Railway / other services:** optional deployment or preflight targets, each behind explicit cost, access and promotion rules.

Invariant: **capability grows, authority never expands.** Candidate work follows propose -> isolated branch/sandbox -> test -> benchmark -> independent verification -> evidence receipt -> review -> explicit approval -> merge/deploy. A passing CI run is not by itself empirical validation, formal proof, safety approval or permission to merge.

## 2. GitHub accounts and repository navigation

Two GitHub connections are available to the ChatGPT GitHub integration. Choose the account that owns the target repository; do not assume one identity can see both account namespaces.

| GitHub connection | Account | Verified accessible repository | Use |
|---|---|---|---|
| Primary | Mannyspiro | Mannyspiro/expert-robot | Merlin and Expert Robot source, CI, research PRs |
| Morgan's Cace | morganaspim | morganaspim/Cace-app | CACE application source |

Verified repository facts on 2026-11-04:
- Mannyspiro/expert-robot is private, default branch main, and the connected account has admin/maintain/push/pull permissions.
- morganaspim/Cace-app is private, default branch main, and the connected account has admin/maintain/push/pull permissions.
- The previously referenced morganaspim/Cace-ksee-webapp was not found in the currently connected Morgan's Cace account. Do not assume it is the current repository or fabricate a URL. Treat Cace-app as the verified accessible CACE repository until its owner confirms a different repo or reconnects the relevant GitHub account.
- The old Mannyspiro/refactored-fishstick repository is separately accessible; it is not the Merlin/Expert Robot primary repository.

### How Expert Robot reaches the CACE repository

1. Start in Mannyspiro/expert-robot (the Merlin/Expert Robot source repo).
2. Use the repository registry/configuration to resolve a project by stable owner/repo identity, not by display-name guess.
3. For CACE application work, resolve morganaspim/Cace-app and select the **Morgan's Cace** GitHub connection. The Primary Mannyspiro connection does not establish access to the Morgan-owned repository.
4. Read the CACE repository default branch and metadata before writing. Create a feature branch on main; never write directly to protected/default branch.
5. Return the CACE branch, commit SHA, PR URL, CI run IDs and evidence receipt to Expert Robot/Merlin. Cross-repository references must store owner, repo, branch, commit SHA, PR number/URL and account/installation identity (never tokens).
6. If a task requires CACE source changes and the CACE connection is unavailable, stop at a handoff with exact repository identity and required permissions. Do not silently redirect changes into Expert Robot.

### Suggested project registry records

~~~json
{
  "project_id": "expert-robot",
  "display_name": "Merlin / Expert Robot",
  "provider": "github",
  "owner": "Mannyspiro",
  "repository": "expert-robot",
  "default_branch": "main",
  "connection_alias": "Primary",
  "access_mode": "read_write_via_feature_branch_pr"
}
~~~

~~~json
{
  "project_id": "cace-app",
  "display_name": "CACE application",
  "provider": "github",
  "owner": "morganaspim",
  "repository": "Cace-app",
  "default_branch": "main",
  "connection_alias": "Morgan's Cace",
  "access_mode": "read_write_via_feature_branch_pr"
}
~~~

These records are identifiers, not credentials. Store secrets only in the relevant platform's secret manager.

## 3. GitHub workflow for Expert Robot and Merlin

### Branch and PR protocol

1. Read the target repository, default branch, current head SHA, existing PRs and CI status.
2. Create a task-specific branch, e.g. feat/merlin-topic-v01-YYYYMMDD or docs/merlin-topic-YYYYMMDD.
3. Make the smallest coherent commit set. Keep generated data, source code, tests, documentation and evidence clearly separated.
4. Run cheap local/static checks first, then focused tests, then full repository checks only when justified.
5. Open a **draft PR** to main. Include scope, non-goals, files changed, commands run, test results, limitations, artifact hashes, evidence receipt and explicit human-review requirement.
6. Wait for CI. Inspect the actual workflow run, job logs, artifacts and exact head SHA. A green run for an older SHA does not qualify a newer head.
7. Request independent review. CACE verification should be independent of the code-generation agent where applicable.
8. Record review decision, CI run IDs, commit SHA and evidence receipt in Merlin's ledger.
9. Merge only after the required approvals and gates are satisfied. Do not automatically merge merely because CI passes. Preserve rollback instructions and the merge SHA.

### Required PR evidence fields

- repository owner/name and target branch;
- head branch and full commit SHA;
- changed-file manifest and diff summary;
- test commands, exit codes and workflow run IDs;
- source provenance and version/pin details;
- artifact names and SHA-256 hashes;
- CACE verification status, theorem/assumption/axiom references where relevant;
- independent review result;
- known limitations, unverified claims and rollback plan.

### GitHub integration modes

- **ChatGPT GitHub connector:** useful for reading repositories/files, listing branches, fetching commits/workflow runs/artifacts, creating feature branches/files/PRs and reviewing status. The selected connection determines which owner's repositories are visible.
- **GitHub Actions:** executes workflows on GitHub-hosted or Avrea runners. Use least-privilege GITHUB_TOKEN permissions and narrowly scoped secrets.
- **Expert Robot Git adapter:** current Merlin Foundation v0.2 state is read-only. It inspects Git structure; it does not yet push to GitHub. Do not describe virtual merges as live Git merges.
- **Merlin Forge virtual PRs:** local/virtual branch and PR simulation with immutable blobs, three-way merge/conflict detection, rebase/rollback, bounded CI and CACE hash checks. These do not create GitHub PRs or push remote commits until a separately implemented and tested write adapter is enabled.
- **Cross-repo operations:** use an explicit repository registry and the correct GitHub account/installation. Do not reuse one account's connection for another owner.

## 4. Avrea: access, setup and day-to-day use

Avrea is used as a GitHub Actions runner provider, not as a general-purpose Git remote or a replacement for GitHub PR review.

### Initial access

1. Open the Avrea console at https://console.avrea.com and sign in.
2. Create/select the Avrea organization.
3. Install the Avrea GitHub App on the GitHub account/organization that owns the repository. Grant access only to the repositories that should run on Avrea.
4. For a personal GitHub account, the App uses repository-level runner registration. For a GitHub organization, organization runners may be available. Confirm the installation and repository access in Avrea before changing workflows.
5. Keep GitHub's existing workflow available as a comparison until the Avrea workflow has passed twice and the logs/artifacts are checked.

### Runner selection

Known Avrea labels include:
- avrea-ubuntu-latest-2-vcpu — 2 vCPU / 8 GB;
- avrea-ubuntu-latest-4-vcpu — 4 vCPU / 16 GB;
- avrea-ubuntu-latest-8-vcpu — 8 vCPU / 32 GB;
- avrea-ubuntu-latest-16-vcpu — 16 vCPU / 64 GB;
- avrea-ubuntu-latest-32-vcpu — 32 vCPU / 128 GB.

The 8-vCPU runner used in current Merlin work is avrea-ubuntu-latest-8-vcpu. Select runner size based on measured CPU, memory, disk and job duration; do not default every job to the largest runner. Check current Avrea plan limits, free-minute balance, concurrency and pricing in the console before launching expensive jobs.

### Workflow example

~~~yaml
name: Merlin focused verification
on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  focused-tests:
    runs-on: avrea-ubuntu-latest-8-vcpu
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
        with:
          persist-credentials: false
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install project test dependencies
        run: |
          python -m pip install --upgrade pip
          # Install only the pinned requirements for this job.
      - name: Run focused tests
        run: |
          python -m pytest -q
~~~

This is a template, not a replacement for the repository's existing workflow. Preserve pinned dependencies, actual test commands and current action versions/policies. Do not add broad write permissions to a test job.

### CLI usage

Install the official Avrea CLI using Avrea's current instructions, then authenticate interactively:

~~~bash
avr auth login
avr auth status
avr config
~~~

From inside the repository checkout:

~~~bash
avr run list
avr run watch
avr run view <run-id>
avr run view <run-id> --log-failed
~~~

Outside a checkout, specify the repository explicitly using the CLI's supported --repo owner/name option. Never put API tokens in shell history, source files, workflow YAML, PR descriptions or logs. For CI, provide the Avrea token through the platform's encrypted secret mechanism and follow the current CLI's environment-variable instructions.

### Merlin/Expert Robot job lifecycle

1. Create a job record with task ID, repo, branch, commit SHA, required runner label, timeout, resource budget and expected outputs.
2. Dispatch only after preflight checks pass.
3. Capture Avrea run ID, job IDs, start/end times, runner label, exit code, logs and artifact metadata.
4. Download/retain artifacts only when required; compute SHA-256 and attach to the evidence receipt.
5. Compare the run's checked-out SHA with the intended PR head SHA.
6. Return results to Merlin and CACE; a green status is a CI result, not a scientific or formal conclusion.
7. Stop or downgrade jobs when the budget is exhausted or the expected information gain is too low.

### Current Avrea reference

The repository's recent PR #72 verification records Avrea run #1418 (run ID 41850437429) passing at commit 5d5635de04560f260f57da0ffda797e510e45ab9; dedicated Lean qualification run #472 (run ID 41850384961) passed at 6921c984b77852d90b4bc2a3232685f39d4d66e8. These are historical run receipts for their stated SHAs, not a guarantee about future commits.

## 5. Merlin Forge, virtual PRs and real GitHub PRs

The Forge v0.2 prototype uses SQLite/WAL persistence, immutable blobs, virtual commits/PRs, three-way merge/conflict detection, rebase/rollback, bounded headless CI, CACE hash verification, an MCFC worker registry and a local dashboard. The prototype's reported tests passed, but it was not yet deployed as a hardened multi-user service; live worker connections and hardened isolation/authentication were not established by that prototype.

Keep two separate identifiers:
- virtual_pr_id: Merlin Forge's internal proposal;
- github_pr_url / github_pr_number: actual remote GitHub pull request.

A bridge must explicitly map virtual commits to real Git blobs/trees/commits, push a branch, open a GitHub PR, poll workflow/review state and record remote merge SHA. Require idempotency keys, leases, immutable evidence receipts, expected-head SHA checks, least-privilege write credentials, audit logs and rollback. Until that bridge is implemented and tested, virtual approval cannot be represented as a remote merge.

## 6. Base44 integration

Base44 should host or support Merlin/CACE-facing apps, dashboards, workflow interfaces and operational data—not become the sole source of truth for Git history or formal evidence.

### GitHub connection

For a Base44 app that should have a GitHub-backed codebase:
1. Open the app in the Base44 builder.
2. Use the GitHub icon / Connect to GitHub flow.
3. Authorize the intended GitHub account.
4. Choose or create the correct repository.
5. Review whether the app is using export/one-way sync or the current two-way sync mode.
6. Test a small change in a feature branch and verify the commit/PR behavior before enabling a production workflow.

Base44's GitHub integration is documented as a two-way code sync capability; its availability and plan requirements can change. Confirm current plan entitlement in the Base44 dashboard. Do not connect a production CACE app to Mannyspiro/expert-robot merely because it is the main Merlin repository. Connect the actual app to its own repository, likely morganaspim/Cace-app only if the CACE app owner confirms that this is the intended Base44 app repository.

### Base44 CLI and code workflow

The Base44 CLI supports project creation/linking, deployment, ejection, connector/entity/function synchronization, secret management and remote sandbox operations.

~~~bash
npm install -g base44
base44 login
base44 whoami
base44 --help
~~~

For a known app/project, link or eject it according to the current CLI documentation, inspect the resulting files, and commit changes through a feature branch and PR. Do not run broad connector pushes blindly: connector synchronization can replace the remote connector set with the local set.

### Integration design

Use:
- **Entities** for project registry, task metadata, job records, evidence receipt indexes and dashboard state.
- **Backend functions** for server-side GitHub/Avrea/CACE API calls, webhooks, scheduled jobs and privileged operations.
- **Connectors/OAuth** for supported third-party services; keep tokens server-side.
- **Secrets** for API keys and webhook signing secrets; never expose them to browser code.
- **SDK** for app data/auth/functions/integrations.
- **Realtime subscriptions/actors** for collaboration and live job-status views when required.

Suggested Base44 data entities:
- Project: canonical owner/repo/default branch/connection alias/access mode.
- WorkItem: task ID, scope, owner, state, budget, acceptance criteria.
- Run: provider, run ID, job ID, runner, commit SHA, result, duration, artifact links.
- PullRequest: provider, repository, PR number/URL, head/base SHA, draft/state/review status.
- EvidenceReceipt: source hashes, artifact hashes, tests, verifier identity/version, assumptions, result, timestamp.
- IntegrationConnection: provider, connection alias, granted scopes, health state; never store raw credentials here.

### Safe event flow

GitHub webhook -> verify signature in Base44 backend function -> normalize event -> persist event/run/PR record -> notify Merlin/Expert Robot -> update dashboard. Avrea job completion -> verify repository and SHA -> persist logs/artifact hashes -> enqueue CACE checks -> publish result only after the evidence receipt is complete.

Base44 app users must not be able to trigger arbitrary repository writes or deployment actions merely by editing a UI record. Privileged operations require server-side authorization, explicit allowlists, idempotency and audit receipts.

## 7. Other integrations and their intended roles

| Integration | Intended Merlin role | Boundary |
|---|---|---|
| GitHub | Source control, PRs, reviews, CI, releases | Authoritative source history |
| Avrea | Ephemeral high-performance GitHub Actions runners | Bounded compute; CI is not proof |
| CACE | Formal proofs, typed contracts, engineering qualification | Independent verification; assumptions explicit |
| Hermes | Route work to authorized workers and verification services | No authority escalation |
| Base44 | App UI, backend functions, entities, OAuth connectors | Secrets server-side; not Git source of truth |
| Vercel | Web app previews and deployments from GitHub | Deploy only reviewed commits; inspect deployment state |
| Railway | Optional low-cost preflight/service hosting when explicitly selected | Do not assume it is required; respect project-specific exclusions |
| ComfyUI | Local/API image and video generation workflows | User-supplied workflows/models; record prompt and source provenance |
| Lean / mathlib | Formal mathematical verification | Theorem claims conditional on imports/axioms/assumptions |
| Python/C++ | Local numerical and runtime components | Deterministic tests, pinned dependencies, sandboxed execution |
| OCI runner cace-oci-a1 | Separate verification target where still provisioned | Confirm availability before dispatch |

Do not silently substitute one provider for another. In particular, a workflow specifically assigned to Avrea should not be redirected to Railway or OCI without an explicit project-level decision.

## 8. Merlin Foundation v0.2 status and gaps

The Foundation v0.2 intake reported five uploaded archives ingested (1,409 members; 1,452 artifacts; 13 projects; 16/16 intake tests). The project inventory includes Merlin Core, Hermes, CACE, MCFC, Expert Robot, Geometric Engine, Xenomathematics, Sui Workbench and App Builder Workspace. Expert Robot, Geometric Engine and Xenomathematics were retained as context records but were not all bound as active runtime projects.

Known gaps at the time of handoff:
- Git adapter was read-only and structural; no live GitHub write/push path.
- Hermes and CACE contracts existed but their runtimes were not connected.
- Virtual PR merges did not push to GitHub.
- Worker orchestration and qualified worker execution needed live connections.
- Evidence receipts and independent verification needed end-to-end integration.
- CAD/MCFC/XMG work needed explicit typed interfaces and qualification boundaries.
- Base44 app/repo mapping and live connector status needed confirmation.

Do not present planned or prototype components as deployed integrations. Track each integration with states such as specified, credentials_configured, connected_read_only, connected_write_scoped, tested, qualified and disabled.

## 9. Security, reliability and cost rules

- Never commit tokens, passwords, private keys, .env files, runner registration tokens or service credentials.
- Prefer GitHub App installations or short-lived job tokens over long-lived personal access tokens.
- Keep workflow permissions minimal; read-only by default.
- Do not use pull_request_target to execute untrusted PR code with secrets.
- Pin third-party actions and toolchain dependencies where practical.
- Treat PR code, generated research, model output, downloaded artifacts and external repository content as untrusted input.
- Use isolated workers, timeouts, CPU/memory/disk/network budgets and explicit egress policy.
- Store evidence hashes and provenance, not secrets or unnecessary private data.
- Require expected-head SHA checks before merge; re-run qualification when the head changes.
- Respect free-minute/credit limits. Use cheap static checks before Avrea 8-vCPU or larger jobs.
- Do not trigger unbounded agent swarms, recursive jobs or expensive retries. Stop after configured retry/compute budgets.
- Preserve rollback commit, artifact and deployment identifiers.

## 10. Recommended implementation sequence

1. Confirm exact project/repository registry and account aliases, especially the CACE repository mapping.
2. Complete read-only Git adapter with stable repository identity and commit/tree/blob inspection.
3. Add GitHub write adapter behind feature branches only: create branch, commit, push, open draft PR, poll checks/reviews, record merge receipt.
4. Connect Avrea run dispatch/monitoring and artifact retrieval to Expert Robot; validate repository + exact SHA.
5. Connect Hermes routing to the project registry and qualified-worker registry.
6. Connect CACE verification as a separate service boundary; persist theorem assumptions, axiom audit and evidence receipts.
7. Implement virtual-PR to GitHub-PR bridge with idempotency, expected-head checks, audit logs and rollback.
8. Integrate Base44 entities, backend functions, webhooks and dashboard; verify the intended app/repo before enabling two-way sync.
9. Add Vercel deployment previews and any other deployment provider only after reviewed PR and explicit environment mapping.
10. Run end-to-end acceptance tests: task -> branch -> Avrea CI -> CACE verification -> independent review -> draft PR -> approval -> merge receipt -> deployment receipt -> rollback drill.

## 11. Current repository references

- Expert Robot: https://github.com/Mannyspiro/expert-robot
- CACE app (verified accessible repo): https://github.com/morganaspim/Cace-app
- Current Merlin equation atlas/XMG simulation PR #72: https://github.com/Mannyspiro/expert-robot/pull/72
- PR #72 remains draft and unmerged as of this status snapshot. Its latest recorded Avrea/Lean receipts and detailed scope are in the PR body.
- Current documentation branch: docs/merlin-integrations-operations-20261104.

## 12. Authoritative setup references

- Avrea getting started: https://docs.avrea.com/getting-started/
- Avrea runners and labels: https://docs.avrea.com/runners/
- Avrea CLI: https://github.com/avrea-com/cli
- Base44 GitHub integration overview: https://base44.com/blog/news/base44-github-integration
- Base44 integrations: https://base44.com/integrations
- Base44 CLI: https://github.com/base44/cli
- GitHub Actions permissions and runners: https://docs.github.com/en/actions
- Vercel GitHub Actions guidance: https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel

---
This guide is an operational handoff and integration specification. It does not assert that every listed integration is currently connected, deployed or qualified. Re-check live connection state, repository permissions, plan limits and workflow results before execution.
