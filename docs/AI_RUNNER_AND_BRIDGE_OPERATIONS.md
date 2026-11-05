# Merlin runner and bridge operations guide

**Purpose:** make the Merlin / Expert Robot / CACE runner network discoverable and reproducible by any coding agent that has authorized GitHub access. This document is the operational entry point; workflow YAML and exact-run evidence remain authoritative.

**Safety invariant:** capability grows; authority never expands. Runner availability is not permission to dispatch. Do not dispatch qualification work, merge, deploy, rotate credentials, or promote research without the required human/policy approval.

## 1. Read order for every AI agent

1. `AGENTS.md` — repository rules and non-negotiable boundaries.
2. This document — runner inventory, bridge flow, credentials *names*, and recovery steps.
3. [Merlin / Avrea / Hermes routing](MERLIN_AVREA_HERMES_ROUTING.md) — routing and proof semantics.
4. [Bidirectional CACE bridge](cace-bidirectional-bridge.md) — trust and return-path policy.
5. The exact workflow files referenced below.
6. The request, result, logs, and manifest for the exact run being investigated.

Never treat a handoff, README, cached chat summary, prior workflow run, or a branch name as proof of current state. Fetch the live branch head and workflow files first. Record the full commit SHA, workflow run ID, run attempt, workflow ID/ref, artifact IDs and digests.

## 2. Repository and branch map

| Role | Repository | Branch / ref | Canonical paths |
|---|---|---|---|
| Orchestrator, task source and return evidence | `Mannyspiro/expert-robot` | `feat/hermes-routing-eval-avrea-discovery-20261105` | `.github/workflows/external-free-runner-bridge.yml`, `.github/workflows/ci.yml`, `python/merlin/`, `docs/evidence/` |
| CACE runner execution and qualification | `morganaspim/Cace-app` | per-request `cace-request/<request-id>` branch, based on `repair/oci-disk-diagnostics-20261105` (derived from `executor/expert-robot-bridge`) | `bridge/request.json`, `bridge/expert-robot-source.tar.gz`, `.github/workflows/expert-robot-bridge.yml` |
| CACE persistent source and policies | `morganaspim/Cace-app` | `main` | `AGENTS.md`, `CACE_AGENT_BOOTSTRAP.json`, `docs/`, `schema/`, `cace_studio/core/` |

The CACE `executor/expert-robot-bridge` branch is the canonical workflow source. CACE owns `.github/workflows/expert-robot-bridge.yml` there. For the current read-only disk investigation, the Expert Robot dispatcher uses the isolated CACE branch `repair/oci-disk-diagnostics-20261105`, derived from that canonical branch; request branches inherit its diagnostic-only workflow change. For each workflow attempt, Expert Robot creates a unique `cace-request/<request-id>` branch from that base and pushes only that request's archive and request envelope. The CACE workflow already listens on `cace-request/**`; its publisher writes results to a separate `cace-result/<request-id>` branch. This avoids rebasing or overwriting a shared request branch and keeps each request/result pair isolated. Never generate a duplicate CACE workflow, delete prior evidence, or rewrite the canonical executor branch. Durable product documentation and policy belong on CACE's default branch.

## 3. Runner inventory

### A. Avrea hosted Linux runner

- GitHub Actions label: `avrea-ubuntu-latest-8-vcpu`.
- Observed runner identity: `avrea-exe-01a1ac6b4ea176b9a41efe2383196a5e`.
- Observed platform: Linux x86_64 / amd64; the CI workflow records `RUNNER_NAME`, `RUNNER_OS`, `RUNNER_ARCH`, `RUNNER_ENVIRONMENT`, `uname`, and `nproc`.
- Used by Expert Robot CI, workflow lint, and the forward bridge dispatcher.
- The forward bridge workflow uses its repository-scoped `GITHUB_TOKEN` with `contents: write` only to persist validated CACE request/result/log/manifest evidence on the Expert Robot branch. Checkout retains that token for the final fast-forward-only evidence commit. The SSH agent key is used only for CACE-app transport.
- This is a GitHub Actions runner label, not evidence of a direct Avrea API integration. The bridge does not require an Avrea API token.
- Do not assume that a different repository or GitHub account can use the label; verify that the target repository has access to the runner group.

### B. CACE OCI self-hosted ARM64 runner

- GitHub Actions labels: `[self-hosted, cace, oci, aarch64]`.
- Repository: `morganaspim/Cace-app`.
- Workflow job: `qualify` in `.github/workflows/expert-robot-bridge.yml`.
- Request lane: `cace-oci-aarch64`; result qualification lane: `formal-static-arm64`. Qualification is bounded and qualification-only.
- The runner checks the archive, extracts to a temporary directory, checks formal-source safety, verifies exact Lean/Mathlib pins, then runs the Lean root and axiom audit.
- Current pinned formal toolchain in this bridge: `leanprover/lean4:v4.34.0`; Mathlib commit `5ed2965256430c3649e86755f9576b54eca72435`.
- The script checks for at least 2 GiB free disk before installing Lean. A configured cache is not proof that the exact toolchain is present.
- The CACE `qualify` job has `contents: read` and checkout uses `persist-credentials: false`. It is not the publisher and does not receive the Expert Robot reverse deploy key.
- An observed qualification failure was caused by insufficient free disk for the pinned Lean installation. Do not delete unrelated caches or data to force a run; first inspect `df -h`, the exact cache path, and the approved cleanup scope.

### C. CACE GitHub-hosted publisher

- Runner: `ubuntu-latest`.
- Workflow job: `publish-result`, runs after `qualify` with `if: always()`.
- It downloads the CACE qualification artifact, validates the structured result, publishes `bridge/result.json` and `bridge/result.log` on the CACE bridge branch, and may attempt the optional reverse SSH return.
- This is a separate trust/permission boundary from the self-hosted OCI runner. Its `contents: write` permission applies to CACE-app, not to Expert Robot.

## 4. Forward request path: Expert Robot → CACE

Canonical source: `Mannyspiro/expert-robot/.github/workflows/external-free-runner-bridge.yml`.

1. The Avrea hosted dispatcher checks out the exact Expert Robot source with `persist-credentials: true` and job-level `contents: write`, because its final evidence-persistence step pushes the validated evidence directory back to the same Expert Robot branch using the job's `GITHUB_TOKEN`. This is separate from the SSH deploy key used only for CACE-app transport.
2. It prepares a repository-scoped SSH transport key. It prefers `CACE_BRIDGE_SSH_PRIVATE_KEY`; if absent, it falls back to the already-installed legacy secret `RAILWAY_SSH_PRIVATE_KEY`.
3. It packages the current source snapshot (maximum 25 MiB; build directories, `.git`, and formal dependency cache excluded).
4. It creates `bridge/request.json` with schema version 2, request ID, full Expert Robot commit SHA, source branch, return repository, requested lane, and `qualification-only` authority.
5. It fetches `executor/expert-robot-bridge` as the canonical base, creates `cace-request/<request-id>` for this run attempt, and pushes only the new request and source archive. It does not rebase or write to the shared executor branch.
6. The CACE workflow triggers on `cace-request/**` and schedules the OCI ARM64 runner. Its publisher creates `cace-result/<request-id>` for the result envelope and log.

The legacy name `RAILWAY_SSH_PRIVATE_KEY` is historical. In this bridge it is the existing CACE-app Git transport/deploy key. It is **not** a Railway API token, CACE verifier credential, Ed25519 signing key, or proof authority. Do not rename, regenerate, replace, display, or paste the key merely because its name is confusing. The workflow writes it to a mode-0600 temporary file, validates it with `ssh-keygen`, and removes the temporary files at job end.

The private value is not readable through the connected GitHub integration. An AI agent must never try to infer or retrieve it from workflow logs, repository files, or Git history.

## 5. CACE execution and result contract

The CACE workflow's qualification job:

- validates the request/source identity;
- rejects unsafe archive members (absolute paths, traversal, links, devices and FIFOs);
- rejects selected proof escapes in Lean source;
- verifies the exact Lean and Mathlib revisions;
- records runner identity, architecture, CPU/memory/disk context and check output;
- writes a result envelope even when qualification fails, provided the workflow reaches result construction;
- uploads `result.json` and `result.log` as an artifact.

Current producer/consumer contract is **result schema version 3**. The Expert Robot consumer validates, among other fields:

- request ID and exact Expert Robot commit;
- CACE repository, triggering CACE commit SHA, exact workflow-definition SHA, workflow ID/ref/name;
- CACE workflow run ID and run attempt;
- `status` in `pass|fail`, integer exit code, and consistency between them;
- exact log SHA-256 and byte length;
- `authority=qualification-only` and `promotion_authority=false`.

A valid structured `fail` is evidence and must be preserved. It is not a malformed envelope and it must not be converted to a success. A qualification failure should not suppress result construction or artifact upload.

**Important distinction:** schema validation and SHA-256 integrity checks are not signer authentication. Current result envelopes are unsigned unless an independently trusted CACE Ed25519 signer is provisioned and the consumer verifies the signature against a pinned/trusted public key. The SSH deploy key proves only repository transport access. Never describe an unsigned result as cryptographically authenticated or independently CACE-verified.

## 6. Return paths and their current status

There are two distinct return mechanisms. Do not conflate them.

### Primary observed path: Avrea polls CACE bridge branch

The Expert Robot dispatcher polls the exact `cace-result/<request-id>` branch over the existing forward SSH transport, matches the exact request ID, validates the v3 result and log digest, and uploads the returned files as an Expert Robot Actions artifact. This path does not require the CACE reverse deploy key.

The latest recorded CACE publication for request `expert-robot-42054029936-e9e0e4312d61db3a758bbcae6c46dd144649fc55` is:
- Expert Robot source commit `e9e0e4312d61db3a758bbcae6c46dd144649fc55`; originating workflow run `42054029936`, attempt 2.
- CACE workflow run `42060207662`, attempt 1; triggering CACE commit `9b003a125701f40997b2d7353b283fa2032d1828`; result-publication commit `e64c77e552e9ba332959c45b31f598e48f67d234`.
- CACE artifact ID `13432430344`; artifact SHA-256 `8dc5ab188c8fdeddfb60273f74ccba13d8d52fb4837d49d7cbd714d08d0f6031`.
- Result status `fail` (exit code 50): the OCI runner had 1,158,896 KiB free, below the 2,097,152 KiB reserve for pinned Lean 4.34.0.
- The result envelope and log digest validate; the log SHA-256 was independently recomputed. The result is unsigned.
- The result was manually mirrored into Expert Robot evidence files. The updated polling consumer is in the workflow, but an automated run of that consumer against this latest CACE result is still pending.

Use `docs/evidence/cace-roundtrip-42054029936-verification.json` and the adjacent request/result/log files for exact digests and checks. This is integrity-checked failure evidence, not a signed result or a passing qualification.

### Optional reverse SSH path: CACE → Expert Robot branch

The CACE publisher recognizes these CACE Actions secret names, in order:

- `EXPERT_ROBOT_SSH_PRIVATE_KEY`
- `EXPERT_ROBOT_DEPLOY_KEY`
- `CACE_TO_EXPERT_ROBOT_SSH_KEY`
- `EXPERT_ROBOT_DEPLOY_PRIVATE_KEY`

This is a separate deploy key scoped to Expert Robot. It is not the forward CACE-app key. If present, the publisher creates `cace-return/<request-id>` with the result, log and request, and does not merge it.

The reverse-key preparation was observed to fail because none of the supported secret values was configured. The reverse path is therefore **not currently confirmed working**. Do not create placeholder secrets and do not ask an agent to print private material. The Avrea polling/artifact route remains the return path to use until an authorized maintainer provisions and tests a real reverse key.

**Historical failed-push diagnosis:** Expert Robot run `42060896619` on source commit `63781028911d459ac5dc8988e86b7506dc652ab2` prepared the forward key and cloned CACE-app, but the remote rejected a push to the shared executor branch. The exact cause was not established. This is now avoided by creating immutable per-request branches from the canonical CACE workflow base; the shared executor branch is not rewritten.

**Latest verified v3 round trip (2026-11-05):** Expert Robot run `42065974770` on source commit `9b6c57d91e92cbaeb16680831b37a5dae7a8b3c4` published request `expert-robot-42065974770-1-9b6c57d91e92cbaeb16680831b37a5dae7a8b3c4`, polled the matching CACE result branch, validated request/commit/workflow identity and the result-log digest, uploaded artifact `13434936211` (SHA-256 `73ddd8ba0504580de0cdf9affcc5244400a41129a60f7c1051948ff4aa8b5bd8`), and persisted the returned evidence under `.cace/evidence/<request-id>/`. CACE workflow run `42066210507` ran on CACE commit `a338079e6215013be4c574843f53c32b7ba54f72`; result artifact `13434271883` has digest `sha256:a28513826346a01dbe5343ca018c59ec163f14e4d792d4c60f63acfb9b56e0f4`. The CACE publisher succeeded and the Expert Robot bridge completed successfully. Qualification returned **FAIL / exit 50** because only `1,143,544 KB` was free, below the `2,097,152 KB` Lean-install reserve. The result-log digest is `4faa5c716ea5e8db6d55dbace663c07f5200ce3a8c14491ad46ee32d3d8e197f`.

The read-only disk diagnosis found `2.8G` under `/var/lib/cace-cache/elan/toolchains/leanprover--lean4---v4.32.1`, while the expected persistent Expert Robot Mathlib cache directory was empty. The existing Lean 4.32.1 installation may be used by other work; do not delete it without explicit maintenance approval. The latest result manifest is integrity-checked but unsigned: `signature_status=missing`, and signer trust is not established.

An earlier verified v3 cycle (Expert Robot run `42065066165`, CACE run `42065140582`) also completed the same transport and returned an integrity-checked qualification failure. The latest run above supersedes it for current runner diagnostics.

The request branch is `cace-request/<request-id>` and the returned result branch is `cace-result/<request-id>`. The canonical CACE workflow base is `repair/oci-disk-diagnostics-20261105`, derived from `executor/expert-robot-bridge`; it is used only as the workflow/base branch. No shared request branch is rebased or cleaned.

## 7. CI and workflow validation

### Expert Robot CI

Canonical file: `.github/workflows/ci.yml`.

- Runs on `avrea-ubuntu-latest-8-vcpu`.
- Push branch filters include `main`, `feat/merlin-lean-proof-optimization-atlas-20261104`, `feat/hermes-routing-eval-avrea-discovery-20261105`, and `repair/cace-bridge-request-isolation-20261105`.
- Supports `workflow_dispatch` and pull requests (opened, synchronize, reopened, ready_for_review).
- The three focused Python groups are separate steps: Hermes claim routing; proof orchestrator + CACE adapter + optional-verifier smoke; research lifecycle.
- C++ configure/build and CTest follow the focused groups; later research, engineering, CAD, proof-observatory and guardrail suites follow.
- Runner identity and `artifacts/` diagnostics are uploaded with `if: always()` at the end of the job. If an early step fails, later tests are skipped; read the job step list before reporting test counts.
- The recent zero-job runs were not test failures. A malformed multiline `printf` in the workflow YAML was corrected; CI subsequently created real jobs.
- One observed real test failure was a stale phrase assertion in `tests/cace_optional_verifier_smoke.py`; it was aligned with the current no-placeholder-secrets wording. CI run `42066010201` completed all listed CI steps successfully. The latest engineering/SPICE source changes were validated by CI run `42067372603`; the end-to-end ngspice workflow is being added separately. On run `42060905047`, all three focused Python groups, CMake configure/build, and CTest (33/33) passed; the run stopped at the stale bridge regression assertion. The assertion was updated to reflect canonical CACE workflow ownership; the next CI run must verify that correction and continue through later suites.

Workflow lint run `42061294025` completed successfully. Its retained artifact `13432386714` records `lint_exit=0` from actionlint on the CI and external bridge workflows.

### Workflow lint probe

Canonical file: `.github/workflows/merlin-workflow-lint-probe.yml`.

It runs actionlint against the CI and external bridge workflows and uploads the actual linter output. The wrapper must preserve the linter process exit code. A previous probe printed `actionlint_exit=1` but incorrectly returned overall exit 0; that probe was not a clean lint pass. Treat the corrected probe's next run and its uploaded log as the acceptance evidence.

### Hermes-to-Lean, engineering/CAD, and read-only research dashboard

**Hermes → Lean boundary**
- `MerlinEventOutbox` is the durable at-least-once event source with leases, idempotency, retry and explicit acknowledgements.
- `HermesWorker` consumes only `merlin.hermes.task`; it revalidates approval and resource lease immediately before invoking an injected stage handler.
- `build_hermes_stage_handlers` records immutable result bytes in the canonical registry before returning evidence references. Proof-search theorem claims pass through `dispatch_eligible_claim`: the claim router must choose `LEAN_COMPILE`, exact UTF-8 Lean source bytes are hashed and verified in the registry, and only then is the injected Lean dispatcher called.
- A compile result is not a CACE proof receipt. The exact stored source digest is passed to the independent theorem verifier when configured. Missing dispatch/verifier configuration is explicitly blocked; promotion authority remains false.
- CI run `42066010201` passed the focused Hermes routing, proof orchestrator/CACE adapter, research lifecycle, and subsequent full build/smoke suite.

**Engineering IR and CAD**
- `engineering_ir.py` is the typed source of truth for parts, pin geometry, pin ratings, nets and endpoint connectivity. Invalid or out-of-range projects cannot be exported.
- `freecad_bridge.py` creates a FreeCAD macro, FCStd/STEP output targets, and a validated wiring sidecar. `freecad_document_bridge.py` imports the generated STEP file in headless FreeCAD, exports a bounded provenance-labelled mesh, and registers that artifact into the canonical registry and knowledge graph.
- `export_spice_netlist` requires explicit per-component kind/value mappings and a declared ground net; it does not infer electrical values from CAD geometry. The deterministic exporter supports two-terminal R/C/L/V/I components and operating-point analysis. Requested operating-point node values are checked against ngspice's native result table.
- `ngspice_engine.py` rejects shell/control/include/external-file directives, applies a wall-time timeout, and requires `prlimit` to enforce the configured virtual address-space limit.
- **Verified full engineering integration (2026-11-05):** workflow run `42069240351` installed checksum-pinned FreeCAD 1.1.4 AppImage and ngspice 42 on Avrea; generated `merlin_project.FCStd` and `merlin_project.step`, imported the STEP file, produced a mesh (32 vertices / 72 faces), and registered it in the canonical registry/graph as `artifact:2a7e6c495e3693e91ac93d203678030e`. ngspice returned exit 0 and measured the divider midpoint as exactly `2.5 V` (expected 2.5 V). Netlist SHA-256: `0708de6ef700121adacf0b1f799acc0a677da2a6bba53704bd4959c5913ea9fe`; ngspice result SHA-256: `3a5e01e70fc5fe8d3ce33d89208178908a936a907bf7be7107c00322363c23cc`. Evidence artifact `13433224922`, SHA-256 `14fe49cca132007ce4f1fd9e1e3507bb82f5c7e693f556916c4ea35786a374e8`. Promotion authority remains false.
- `.github/workflows/engineering-integration.yml` runs the reproducible Engineering IR → FreeCAD → SPICE → ngspice smoke on Avrea and uploads the source netlist, FCStd/STEP files, imported mesh, registry/graph snapshots, result and SHA-256 manifest.

**Read-only research dashboard**
- `MerlinReadAPI` composes the canonical project registry, hypothesis ledger, knowledge graph and event outbox; it does not create shadow stores or mutate research state.
- `HudActivityWSGI` serves a browser view at `/dashboard` and GET-only APIs: `/api/hud/activity`, `/api/hud/graph`, `/api/hud/node`, `/api/hud/projects`, `/api/hud/project`, `/api/hud/hypotheses`, and `/api/hud/outbox`. The browser uses GET requests only and renders data with text nodes, not injected HTML. HTTP reads do not acknowledge outbox events; the optional event pump is a separate local projection consumer.
- The browser dashboard now combines pipeline phase, agent/resource state, independent CACE verification events, canonical project/artifact inventory, hypothesis ledger, outbox counts, graph nodes and the event timeline. The project selector is populated from the canonical registry; it does not maintain a shadow project list.
- The project index is bounded and includes canonical artifact counts; project detail verifies artifact content hashes before displaying metadata. The graph, hypotheses and outbox views are all sourced from the same injected canonical stores.
- `build_hud_runtime` must receive the actual canonical store instances. The host application remains responsible for authentication, authorization, TLS and loopback/network binding; do not expose the HUD publicly without those controls.
- Registry query, HUD runtime, node/graph, dashboard and outbox read-only contracts are covered by the Expert Robot CI suite.

## 8. How an AI agent should operate this system

### Before acting

1. Confirm the connected GitHub account has access to the intended repository. Use the Expert Robot connection for `Mannyspiro/expert-robot` and the CACE connection for `morganaspim/Cace-app`.
2. Read this guide and the repository's `AGENTS.md`.
3. Fetch the live branch head, workflow file contents and relevant config at the exact ref.
4. Inspect recent workflow runs, jobs, step conclusions, artifacts and logs. A run-level `failure` alone is insufficient to know whether the cause was parsing, queueing, qualification, publishing or return validation.
5. Preserve the full commit SHA, workflow ID, run ID and attempt. Never substitute a branch name or short SHA for provenance.

### For a controlled bridge request

1. Confirm explicit approval for the exact request and lane.
2. Confirm the intended Expert Robot source commit and current CACE bridge branch.
3. Check that the Avrea runner label is available to this repository.
4. Check the existing forward key *by whether the workflow's key-preparation step succeeds*; do not read the secret value.
5. Check the OCI runner is online and has the required disk headroom before dispatch. Do not delete unrelated data.
6. Dispatch only through the documented workflow; do not run Lean directly on the Avrea runner as a substitute for CACE qualification.
7. Wait for a matching request ID. Validate the result schema, source commit, CACE workflow identity, status/exit code, log digest and byte length.
8. Download and preserve the returned artifact. Independently verify any signature only if a trusted signer and public-key policy are configured.
9. Report pass/fail separately from transport success. Keep `promotion_authority=false`.
10. Record the evidence manifest and link to the exact Actions run. Do not merge or promote automatically.

### GitHub UI navigation

- Repository → **Actions** → choose **CI**, **External Free Runner Bridge**, or **Merlin Workflow Lint Probe**.
- Open a run → **Jobs** → select the job → inspect each step and its conclusion.
- Open **Artifacts** on the run summary to download the diagnostics/evidence bundle.
- In CACE-app, inspect the `executor/expert-robot-bridge` branch for the exact request, result, log and generated workflow.
- GitHub Actions → runner settings (where authorized) to inspect runner online/offline status and labels. A repository-scoped integration may not have runner-administration permission; report that limitation rather than guessing.

### Useful API reads

Use the connected GitHub integration's supported read operations or GitHub REST GET endpoints:

- `GET /repos/{owner}/{repo}/actions/runs?branch={branch}`
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}`
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/jobs`
- `GET /repos/{owner}/{repo}/actions/runs/{run_id}/artifacts`
- `GET /repos/{owner}/{repo}/actions/jobs/{job_id}/logs`
- `GET /repos/{owner}/{repo}/contents/{path}?ref={branch}`

A connected GitHub tool may be read-only for workflow dispatch, secrets, runner administration or environment configuration. Do not claim these operations are available unless the connected tool explicitly exposes them. Never call an unsupported endpoint by guessing.

## 9. Troubleshooting map

| Symptom | First evidence to inspect | Correct response |
|---|---|---|
| Run exists but has zero jobs | workflow YAML, event, branch/path filters, job-level `if`, permissions | Fix parse/condition issue; do not call it a test failure |
| Avrea job remains queued | runner label access and runner group availability | Wait/check availability; do not invent runner execution |
| Key preparation fails | step log and secret-name fallback path | Keep existing key; do not print or regenerate it |
| CACE job fails before Lean | archive validation, source safety, disk preflight | Preserve structured failure; diagnose the specific preflight |
| Lean install fails for disk | `df -h` output and exact cache path | Request approved storage/cache maintenance; do not delete unrelated data |
| Result envelope validation fails | request/result JSON, schema version, CACE run identity, log hash/size | Reconcile producer and consumer contracts; keep failed results structured |
| Reverse-key step fails | supported secret *names* and step result | Use forward polling path; configure reverse key only through authorized maintainer |
| Artifact upload succeeds but workflow is red | qualification status and final enforcement step | Distinguish valid qualification FAIL from transport/envelope failure |
| CI stops after a focused group | exact failed step and uploaded diagnostics | Fix that failure, then rerun to reach C++/CTest and later suites |
| Linter says pass but log shows nonzero | wrapper exit-code handling | Treat as failed lint; fix wrapper before trusting status |

## 10. Acceptance checklist

A complete, successful vertical slice requires all of the following on a single traceable request:

- [ ] Explicitly approved request and exact Expert Robot source commit.
- [ ] Avrea dispatcher job actually ran; runner identity retained.
- [ ] CACE bridge request references the exact source commit and request ID.
- [ ] OCI ARM64 runner actually ran with recorded identity and exact Lean/Mathlib pins.
- [ ] CACE result schema validates for both `pass` and `fail` paths.
- [ ] CACE result binds CACE repository, full commit, workflow ID/ref/run/attempt and log digest/size.
- [ ] Returned result bytes and log bytes match the CACE artifact; request ID matches.
- [ ] Trusted Ed25519 signature verifies against a pinned trusted signer, if claiming authenticated CACE provenance.
- [ ] Evidence artifact and manifest are preserved in Expert Robot.
- [ ] Independent verification is reported separately from compilation, transport and qualification.
- [ ] No automatic merge, theorem promotion, or authority expansion.

Until every required box is evidenced, describe the bridge as partially operational and name the missing step. A valid `fail` round trip is a transport/schema success and a qualification failure—not an end-to-end qualification pass.
