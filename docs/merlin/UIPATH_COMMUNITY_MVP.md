# Merlin on UiPath Studio Community Edition — MVP Build Specification

**Status:** implementation specification / first build increment  
**Target repo:** Mannyspiro/expert-robot  
**Branch:** feat/merlin-uipath-community-mvp-20261104  
**Execution model:** local attended Windows robot first; optional Studio Web/API workflows later.

## 1. Product decision

Use UiPath Studio Community Edition as Merlin's desktop automation and workflow-execution surface. Do not attempt to reimplement Merlin's research reasoning, Git object model, proof engine, project registry, or worker scheduler as giant UiPath sequences.

UiPath is the deterministic automation layer:
- UI automation when a human-facing desktop application has no suitable API.
- API calls for GitHub, Base44, and supported service endpoints.
- Process orchestration for local tools such as Git, Python, Lean, CAD utilities, and the Avrea CLI.
- Document and archive handling.
- Human approval checkpoints.
- Execution logs and evidence-receipt production.

Merlin remains the project/research authority; Expert Robot remains the agent and execution gateway; GitHub remains source control; Avrea supplies CI compute; CACE verifies proofs/engineering claims; Hermes routes work; Base44 can provide the web dashboard and app backend.

Invariant: **capability grows, authority never expands.** UiPath workflows may prepare changes and open draft PRs. They must not merge, deploy to production, alter access controls, or expand credentials automatically.

## 2. Platform and licensing assumptions

- UiPath Studio Desktop is Windows-only. Use the official Community Edition installer and Community activation.
- Studio Web is the browser-based alternative for API-first workflows and is available on macOS/Windows. It is not a substitute for Windows desktop UI automation.
- Start with local attended runs and manually initiated workflows. Confirm current Community entitlements, monthly credits, robot availability, and Automation Cloud quotas in the UiPath account before relying on cloud orchestration or unattended runs.
- Do not assume a paid Orchestrator plan, Integration Service connector entitlement, or unattended execution quota.
- No paid trial, card trial, or paid dependency is required for the initial local MVP.

Official install: https://docs.uipath.com/studio/standalone/latest/user-guide/install-studio  
Community developer access: https://www.uipath.com/developers  
Studio overview: https://www.uipath.com/product/studio

## 3. Solution layout

Create a UiPath Windows project named **Merlin.Automation** in this repository:

~~~text
uipath/
  Merlin.Automation/
    README.md
    project.json                 # generated/maintained by Studio
    Main.xaml                    # entry point / dispatcher
    Config/
      Config.json                # non-secret defaults only
      Config.schema.json
    Data/
      task.schema.json
      evidence-receipt.schema.json
    Workflows/
      Initialize.xaml
      LoadTaskQueue.xaml
      ValidateTask.xaml
      RouteTask.xaml
      GitHub/
        ResolveRepository.xaml
        ReadRepositoryState.xaml
        CreateFeatureBranch.xaml
        OpenDraftPullRequest.xaml
        ReadPullRequestChecks.xaml
      Avrea/
        DispatchAvreaWorkflow.xaml
        MonitorAvreaRun.xaml
        CollectAvreaArtifacts.xaml
      CACE/
        RunLeanQualification.xaml
        ValidateEvidenceReceipt.xaml
      Research/
        IntakeArchive.xaml
        ExtractDocumentMetadata.xaml
        RegisterResearchArtifact.xaml
      Engineering/
        LaunchCadApplication.xaml
        CaptureEngineeringArtifact.xaml
      Approvals/
        RequestHumanApproval.xaml
      Evidence/
        CreateEvidenceReceipt.xaml
        HashArtifacts.xaml
      Common/
        InvokeHttpJson.xaml
        InvokeProcess.xaml
        WriteStructuredLog.xaml
    Tests/
      TestTaskValidation.xaml
      TestRepositoryRouting.xaml
      TestEvidenceReceipt.xaml
    Assets/
      README.md                  # no credentials committed
~~~

Studio should generate the initial project manifest and workflow scaffolding for the installed Studio/activity-package versions. Commit the generated files and lock/pin package versions after a clean Studio restore.

## 4. Core execution architecture

Main.xaml is a small dispatcher, not the whole application.

1. Initialize configuration and structured logging.
2. Load one task from the local queue or an approved API endpoint.
3. Validate the task schema, project identity, allowed operation, budget and acceptance criteria.
4. Resolve the repository/service from the project registry.
5. Route to one reusable workflow.
6. Capture outputs, logs, process exit codes and artifact hashes.
7. Ask for human approval for consequential actions.
8. Persist an evidence receipt and update task state.
9. Return to idle or process the next bounded task.

Use a State Machine or Flowchart for explicit states:
Idle -> Load -> Validate -> Plan -> AwaitApproval (if needed) -> Execute -> Verify -> Receipt -> Complete.
Failures route to Quarantined with diagnostics; they must not silently retry forever.

## 5. Task contract

Every task should use a typed JSON envelope. Example:

~~~json
{
  "schema_version": "1.0",
  "task_id": "merlin-task-example-001",
  "project_id": "expert-robot",
  "operation": "github.prepare_draft_pr",
  "repository": {
    "owner": "Mannyspiro",
    "name": "expert-robot",
    "connection_alias": "Primary"
  },
  "source": {
    "branch": "main",
    "expected_head_sha": "REQUIRED_AT_RUNTIME"
  },
  "parameters": {},
  "budget": {
    "max_attempts": 1,
    "timeout_seconds": 900,
    "max_artifact_mb": 100
  },
  "approval": {
    "required": true,
    "action": "open_draft_pr"
  },
  "acceptance": [
    "repository identity matches project registry",
    "working branch is not the protected default branch",
    "evidence receipt is persisted"
  ]
}
~~~

The example SHA is deliberately a runtime placeholder, not a valid pinned commit. Reject tasks with missing or stale expected SHAs when a write operation depends on repository state.

Allowed operation names should be an explicit allowlist, not arbitrary workflow names or user-supplied process commands.

## 6. Initial workflow set

### A. Archive intake — first MVP workflow

IntakeArchive.xaml
- Accept one archive path from an approved intake folder.
- Record original filename, size, SHA-256 and intake timestamp.
- Extract into a new isolated task-specific folder; prevent path traversal and reject unsafe archive entries.
- Enumerate files, classify extension/type, compute hashes, and produce a manifest.
- Do not execute extracted files, macros, scripts or binaries.
- Deduplicate by content hash; preserve original archive and source provenance.
- Register the manifest with Merlin's project registry.
- Emit an intake receipt and counts.

### B. GitHub repository state — read-only first

ResolveRepository.xaml and ReadRepositoryState.xaml
- Resolve owner/repository using an exact registry record and account connection alias.
- Read default branch, current head SHA, open PRs, branch and workflow status.
- Never guess repo identity from a display name.
- If the requested owner is Morgan's CACE account, select the separate Morgan's Cace connection and resolve morganaspim/Cace-app; do not silently use the Mannyspiro connection.
- Known accessible repositories must be rechecked at runtime; the registry is not a substitute for live permission checks.
- Persist the source SHA and timestamp for all subsequent operations.

### C. Draft PR preparation — guarded write workflow

CreateFeatureBranch.xaml and OpenDraftPullRequest.xaml
- Only operate on a configured repository allowlist.
- Require explicit task authorization and a fresh expected-head SHA.
- Create task-specific feature branch from the verified base SHA.
- Never commit to main or another protected default branch.
- Open draft PR only; do not merge.
- Require human confirmation before opening the PR if the task policy says approval is required.
- Record PR URL, PR number, branch, commit SHA and action receipt.
- Treat a head SHA change as invalidating prior test/verification receipts.

The initial MVP can call GitHub's REST API via an HTTP Request activity or a small reviewed local helper. Use a GitHub App or short-lived scoped token where available. Store credentials in an approved secret/credential store, never in Config.json, XAML, arguments, logs, or Git.

### D. Avrea dispatch and monitoring

DispatchAvreaWorkflow.xaml, MonitorAvreaRun.xaml, CollectAvreaArtifacts.xaml
- Dispatch only a named, pre-existing workflow in an allowlisted repository.
- Verify branch and exact commit SHA before dispatch.
- Use Avrea CLI as a process invocation or its documented API; do not scrape the UI if a structured CLI/API response exists.
- Capture run ID, job IDs, runner label, status, duration, exit code, logs and artifact metadata.
- Stop polling at the task deadline and mark timed out; do not create an unbounded retry loop.
- Verify artifacts belong to the expected repository and SHA before attaching them to the receipt.

### E. CACE / Lean qualification

RunLeanQualification.xaml
- Execute only an allowlisted command in a configured working directory.
- Capture Lean version, mathlib revision, source commit SHA, exact command, exit code, stdout/stderr and run duration.
- Keep assumptions, axioms, imported modules and theorem status explicit.
- A passing Lean build is evidence of compilation/checking under recorded dependencies, not proof that the mathematical model or its physical interpretation is correct.
- Route the report to CACE for independent review where configured.

### F. Research intake

- Retrieve sources through permitted public APIs or approved connectors.
- Save source URL, publisher, publication date, retrieval timestamp and content hash.
- Separate extracted statements from Merlin's own hypotheses.
- Track claims, evidence, uncertainty, counterexamples and review status.
- Do not treat model-generated summaries as primary evidence.

### G. CAD and engineering automation

- Use APIs/file formats first where possible; use desktop selectors only when UI interaction is necessary.
- Keep CAD edits in copies or feature branches.
- Capture source file hash, application/version, units, coordinate frame, component library version and export settings.
- Generate wiring/BOM/diagram outputs as artifacts and run independent checks before promotion.
- Never infer engineering correctness from a successful UI sequence.

## 7. Integration patterns

### GitHub
Use REST API calls for repository metadata, refs, commits, pull requests and workflow runs. The selected GitHub account/connection must match the repository owner. Use branch-first writes and draft PRs. GitHub is the canonical history; Merlin virtual PR IDs are separate from actual GitHub PR numbers.

### Avrea
Invoke the official avr CLI or supported API. Capture structured outputs and exact run IDs. Prefer low-cost static checks before selecting a larger runner. Current commonly used label in the project context: avrea-ubuntu-latest-8-vcpu; verify live labels, quota and pricing before dispatch.

### CACE
Use a stable API/file contract to submit verification requests and retrieve signed or hashed receipts. Keep theorem assumptions and axiom audit data in the result.

### Base44
Use Base44 backend functions/entities for project/task/run/evidence dashboard state. UiPath may call an authenticated backend endpoint; do not expose Base44 secrets in desktop workflows. Webhooks should be signature-verified server-side.

### Hermes
Send typed task envelopes and receive typed route decisions. Hermes selects only registered workers with declared capabilities and budgets.

### Local applications
Use Start Process only with allowlisted executables and fixed argument templates. Do not accept arbitrary executable paths or shell command strings from untrusted task input. Prefer argument collections, working-directory controls, timeouts and captured exit codes.

## 8. Credential and approval model

- No API key, PAT, password, refresh token, runner token or private key in Git.
- Use UiPath credential/asset facilities if available under the current Community entitlement; otherwise use Windows Credential Manager or a user-scoped secret store and retrieve secrets at runtime.
- Do not log credentials or authorization headers.
- Use separate read and write credentials.
- GitHub read-only is the default.
- Write scope is limited to feature branches and draft PR creation.
- Merge, production deployment, access-control changes, destructive file operations and credential changes require a separate explicit human approval.
- External files, web content, PR content and generated code are untrusted inputs.
- Keep a local audit log with task ID, actor, workflow version, input hashes, output hashes, timestamps and action outcomes.

## 9. Evidence receipt format

~~~json
{
  "receipt_version": "1.0",
  "task_id": "merlin-task-example-001",
  "workflow": "Merlin.Automation/Workflows/Avrea/MonitorAvreaRun.xaml",
  "workflow_version": "git-commit-sha",
  "repository": "Mannyspiro/expert-robot",
  "source_commit": "full-sha",
  "provider": "avrea",
  "provider_run_id": "run-id",
  "result": "passed|failed|timed_out|not_run",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "commands": [],
  "artifacts": [
    {
      "path": "relative-artifact-path",
      "sha256": "sha256-value",
      "size_bytes": 0
    }
  ],
  "limitations": [],
  "approval": {
    "required": true,
    "approved_by": null,
    "approved_at": null
  }
}
~~~

The sample values are schema examples, not real run receipts. Receipts should be append-only and tied to exact source and workflow versions.

## 10. Build milestones

**M0 — Studio environment**
- Install Community Edition on a supported Windows machine.
- Create Merlin.Automation Windows project.
- Commit generated project manifest and a minimal Main.xaml.
- Confirm local attended execution and package restore.

**M1 — Safe local automation**
- Implement config loading, task schema validation, structured logging and exception handling.
- Implement archive intake, file manifest, SHA-256 and evidence receipt.
- Add tests for malformed task, missing file, duplicate archive and unsafe archive path.

**M2 — GitHub read-only**
- Resolve both account connections and repository registry.
- Read repo metadata, branches, PRs and workflow runs.
- Verify exact repository owner and source SHA.

**M3 — Avrea + CACE**
- Dispatch one focused Avrea workflow.
- Monitor and retrieve one artifact set.
- Run one Lean qualification command and persist its report.
- Compare all source SHAs before accepting results.

**M4 — Guarded GitHub PR creation**
- Create feature branch and draft PR with a human confirmation step.
- Add CI polling and CACE evidence attachment.
- Keep merge disabled.

**M5 — Base44 + Hermes**
- Connect project/task/run/evidence APIs.
- Show status in Base44 dashboard.
- Route only registered and budgeted tasks.

**M6 — CAD and research**
- Add one CAD workflow and one research-intake workflow.
- Test on copies and compare generated outputs independently.

## 11. Acceptance criteria for the first working Merlin MVP

The MVP is not complete until it can:
1. Start from Studio on Windows as an attended workflow.
2. Validate a typed task and reject malformed/unauthorized operations.
3. Intake an archive without executing its contents.
4. Produce a deterministic file manifest and SHA-256 hashes.
5. Resolve Mannyspiro/expert-robot and morganaspim/Cace-app using distinct configured connections.
6. Read repository state and preserve the exact head SHA.
7. Dispatch and monitor one Avrea workflow against that SHA.
8. Run one configured Lean check and preserve its full provenance.
9. Produce an evidence receipt that links all inputs, outputs and provider run IDs.
10. Open a draft PR only after the configured human approval.
11. Never merge or deploy automatically.

## 12. First local setup checklist

1. On Windows, create/sign in to a UiPath Community account: https://www.uipath.com/developers
2. Download the Community Edition desktop installer from Automation Cloud / Resource Center.
3. Choose the per-user Quick installation unless a specific requirement needs Custom installation.
4. Open Studio, activate Community, and create a Windows project called Merlin.Automation.
5. Add the standard activities needed for file handling, JSON, HTTP, process execution, logging and UI automation using compatible package versions.
6. Create Main.xaml and the first IntakeArchive.xaml workflow.
7. Save the project under the repository's uipath/Merlin.Automation directory.
8. Commit the generated project to a feature branch; do not commit local secrets, caches or machine-specific files.

This repository specification is the implementation contract. It does not claim the Studio project has been installed, executed or validated on the user's Windows machine. The next implementation step is to create and validate the actual Studio-generated project and XAML workflows on a supported Windows Studio installation.
