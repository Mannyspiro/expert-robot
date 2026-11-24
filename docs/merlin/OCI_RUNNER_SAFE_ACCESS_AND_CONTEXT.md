# Merlin cross-repository agent context and OCI runner handoff

**Purpose:** durable, repository-backed context for any coding/research AI continuing Merlin. This document is a navigation and operating contract, not runtime, proof, qualification, or deployment evidence.

## Repositories and roles

- `Mannyspiro/expert-robot`: Merlin orchestration/cognition/research/RSI/math learning, C++ runtime, Python orchestration, agent swarm, reusable skills, benchmark/evidence workflows.
- `morganaspim/Cace-app`: independent scientific/formal verification environment, canonical claim/proof ledger, typed graph execution, reproducibility, evidence/certificates, research canvas and CACE OCI MCP control plane.
- Hermes: decomposition, dispatch, durable outbox, idempotency, acknowledgement, cancellation, deadlines, and result collection.
- MCFC: virtual compute/module fabric, capability registry, leases, budgets, worker scheduling, telemetry, module graph and resource accounting.
- Avrea: external runner lane when currently configured and evidenced. Historical Expert Robot workflows refer to `avrea-ubuntu-latest-8-vcpu`; do not assume availability.
- OCI: CACE ARM64 self-hosted runner lane. Historical label: `[self-hosted, cace, oci, aarch64]`. Do not assume live registration, health, or disk headroom from historical files.

The roles are separate: Hermes routes, MCFC allocates, Avrea/OCI execute, CACE independently verifies, and explicit policy/human approval controls promotion.

## Product and engineering scope

Merlin is intended to provide a persistent conversational/voice agent and an adaptive research canvas/HUD with inspectable agent/job/evidence state, branching research, knowledge graph, artifact provenance, mathematical and engineering visualizations, and controlled tool execution.

Major connected domains:
- mathematics research: induction/discovery, deduction/proof, Lean, numerical experiments, counterexamples, theorem graph, Ideonomy, useful analogies and lacuna-oriented research;
- adaptive mathematics education: mathematician, mathematics programmer, and computational hacker/problem-solver paths; concrete-first lessons, simulations, proofs/algorithms, history of mathematical pioneers, interest-driven video supplements, persistent mastery and retrieval;
- CACE verification: typed claims, exact source/artifact digests, independent verifier receipts, Lean and numerical evidence with explicit scope/assumptions;
- MCFC compute fabric and Hermes task orchestration;
- RSI: isolated candidate generation, test, benchmark, skeptic, qualification, comparison, explicit promotion;
- CAD/FreeCAD: import/export, engineering IR, parts/assemblies, coordinate frames, constraints, materials, tolerances, manufacturability;
- electrical/wiring: typed component/pin/net/harness graph, schematic and netlist generation, safety/thermal/current/voltage/gauge checks, ngspice simulation and versioned evidence;
- image/video generation: generated assets with prompt/provider/provenance/digests; do not confuse image renderings with editable CAD or verified engineering drawings.

These are product goals and architecture requirements, not claims that every adapter/UI is already integrated or production-qualified.

## Expert Robot source map

Useful current source/docs include:
- `README.md`: architecture, cognition, research engine, compute ladder.
- `docs/hybrid-math-engine.md`: agent/skill/memory/authority separation, divergent exploration, skeptic, bounded shortlist, Lean boundary.
- `docs/research-engine.md`: research episodes, QD archive, skill stages, benchmarks, proof lineage.
- `docs/artificial-interoception.md`, `docs/software-neuromodulators.md`, `docs/personality-executive.md`: telemetry-driven search policy; no truth/authority changes.
- `docs/recursive-lemma-factory.md`: bounded recursive helper lemma generation and Lean verification.
- `docs/cace-bidirectional-bridge.md`: isolated forward/reverse bridge; qualification-only evidence; no merge/promotion authority.
- `.github/workflows/external-free-runner-bridge.yml`, `.github/workflows/cace-return-pr.yml`: bridge implementation; inspect exact current contents before any dispatch.
- `.github/workflows/rsi-candidate-qualification.yml`, `.github/workflows/production-rsi-qualification.yml`, `.github/workflows/collared-rsi-generation.yml`: RSI candidate qualification and evidence workflow. Workflow presence does not prove a current runner or successful qualification.
- `python/merlin/` and `tests/test_parrondo*.py`, `tests/test_lesson_renderer.py`, `tests/test_learning_schedule.py`: current mathematics learning work. A lesson descriptor or renderer contract is not proof of a complete browser experience.

## CACE source map

Read `AGENTS.md`, `.agents/AGENTS.md`, `AI_CONTEXT/00_START_HERE.md`, and the active subsystem docs before changing CACE. Canonical navigation includes:
- `CACE_AGENT_BOOTSTRAP.json`
- `docs/MASTER_BUILD_SPEC.md`, `docs/GOAL_REGISTRY.json`, `docs/CHAT_IDEA_LEDGER.md`, `docs/CROSS_CHAT_HANDOFF.md`
- `docs/STATUS.md`, `docs/ARCHITECTURE.md`, `docs/SECURITY_ARCHITECTURE.md`, `docs/BUILD_AND_TRUST_GUIDE.md`, `docs/CLAIMS.md`
- `cace_studio/core/`: typed graph execution, claim/proof governance, verification, certificates, reproducibility and formal bridges.
- `cace_studio/modules/`: registered math/science modules; version labels are not qualification.
- `formal/`: pinned Lean project.
- `schema/`, `collaboration/schema/`, `tests/`: contracts and validation.
- `cace_studio/gui/`, `web/`: presentation/workbench layers; canonical scientific semantics remain in core.

CACE context pulls must stay <=800 files, preferably <=500 source/test files in a deterministic task shard. Do not ingest build outputs, caches, vendored dependencies, generated assets or archives.

## OCI runner: verified source map vs live inventory

### Repository files inspected

The following are tracked in `morganaspim/Cace-app`:
- `ops/oci_mcp/README.md`
- `ops/oci_mcp/server.py`
- `ops/oci_mcp/policy.py`
- `ops/oci_mcp/cace-oci-mcp.service`
- `ops/oci_mcp/cace-oci-mcp.sudoers`
- `ops/oci_mcp/requirements.txt`
- `ops/oci_mcp/install.sh`
- `tests/test_oci_mcp_policy.py`
- `.github/workflow-archive/cace-oci-runner-health.yml`
- `.github/workflow-archive/cace-oci-compute-probe.yml`

Other historical OCI/runner workflows present under `.github/workflow-archive/` include:
- `cace-oci-cleanup-a1.yml`
- `cace-oci-cutover-verify.yml`
- `cace-oci-formal-cache-prewarm.yml`
- `cace-oci-provision-durable-vm-v2.yml`
- `cace-oci-provision-durable-vm.yml`
- `cace-oci-register-cutover.yml`
- `cace-oci-ssh-cutover.yml`
- `cace-oci-vm-start-inspect.yml`
- `cace-runner-diagnostics.yml`
- `cace-runner-persistence-probe.yml`
- `cace-runner-service-install.yml`
- `cace-runner-watchdog.yml`

These workflow files are historical source, not permission to run them. In particular, do not dispatch cleanup, provision, register, cutover, service-install, watchdog, or cache-prewarm workflows.

### What the repository says about the OCI MCP

The CACE OCI MCP is a deliberately narrow MCP server, not a general shell or OCI proxy. It uses an OCI instance principal and is designed to listen on loopback at `127.0.0.1:8765/mcp`. Documented read-only operations:
- capability switches;
- CACE runtime/service health;
- last 1–200 CACE journal lines;
- OCI instance and attached VNIC summary;
- rules on NSGs attached to the VM.

Optional write operations are separately disabled by default:
- restart only `cace-web`;
- add/remove only MCP-managed TCP 80/443 ingress rules on an attached NSG.
No generic shell, IAM mutation, secret access, instance termination, or arbitrary OCI SDK call is exposed. This MCP cannot list or read the VM's complete filesystem.

The systemd unit describes `cace-mcp` as the service account, `/opt/cace-oci-mcp/current` as working directory, `/var/lib/cace-oci-mcp/cache` as cache home, loopback port 8765, and fail-closed write flags. The sudoers file permits only `systemctl restart cace-web`.

**Important installer warning:** `ops/oci_mcp/install.sh` computes a release directory from the source SHA and runs `sudo rm -rf "$release"` before copying the release. Never run this installer against the existing VM as a routine update; a same-SHA run can delete the existing release path. No install/update/restart was performed for this handoff.

### Historical runner-health layout (not confirmed live)

The archived health workflow expected:
- `/opt/actions-runner`
- `/var/lib/cace-cache/elan`
- `/var/lib/cace-cache/xdg`
- `/var/lib/cace-cache/mathlib`
- `/var/lib/cace-cache/telemetry/heartbeat`
- a runner service identified by `/opt/actions-runner/.service`
- `cace-runner-watchdog.service`

The workflow also checked ARM64 architecture, active/enabled services, a heartbeat younger than 120 seconds, RAM, and disk capacity. This is only a historical expected layout. No direct OCI login or read-only VM query was available during this update; none of these paths/services/current values is confirmed to exist now.

### Inventory status and safe next method

- CACE repository tree and selected source files: inspected.
- OCI VM filesystem, runner registration, current disk usage, active jobs, installed packages, model/cache contents, and service state: **NOT_RUN / UNAVAILABLE**.
- No private key or credential material is included in this document.
- No OCI VM command, workflow dispatch, cache operation, write, cleanup, installation, restart, provisioning, or cutover was performed.
- No runner files were copied to GitHub; no existing runner data was changed.

When an authenticated read-only OCI route is made available, inventory in bounded stages:
1. Read instance identity, architecture, current active jobs, filesystem free space and inode headroom.
2. List path names, sizes, owners, mtimes and filesystem boundaries only; do not read secrets or copy files.
3. Exclude credentials, tokens, environment files, SSH private keys, caches with user/model data, and personal data from reports.
4. Read only selected non-secret source/config files, in bounded batches; hash each inspected file and record its path/size/mtime/hash.
5. Do not create archives or duplicate the runner filesystem. Store the manifest in GitHub, not on the OCI disk.
6. Stop if disk headroom is low/unknown, an active job is present, or the read-only route cannot be proven.

## Hard operating constraints

- Do not delete, overwrite, truncate, move, rename, clean, prune, vacuum, reinstall, provision, cut over, restart, or reconfigure anything on the OCI VM or its persistent caches.
- Do not run `rm -rf`, `git clean`, `git reset --hard`, cache eviction, broad package upgrades, full builds, or bulk archive/model/data copies on OCI.
- Keep OCI concurrency at one; do not run duplicate probes/retries. Do not spend Actions/Avrea quota without explicit authorization.
- Never publish credentials or private data in commits, logs, workflow artifacts, or PR comments.
- Use a new isolated documentation branch. Do not merge or deploy without explicit approval.
- Mark all unknown current runtime facts `NOT_RUN` or `UNAVAILABLE`; historical source is not live evidence.

## Current work continuity

The Expert Robot mathematics learning work includes the zero-first Parrondo lesson, typed lesson schema and renderer, three learner paths, concept registry and persistent SQLite spaced retrieval. The existing draft mathematics PR #123 is separate; check live status and do not merge it. Prior CI attempts were cancelled, not passed. Do not describe those tests as successful until a fresh exact-head result exists.

For every continuation, re-check live branch, PR, workflow and commit status. Do not infer current state from this handoff.


## Additional historical OCI access context recovered from prior work

The following is historical context recovered from earlier conversations, not a live OCI observation:
- The runner was previously identified as `cace-runner-a1`; another earlier handoff called it `cace-oci-a1`. Treat the hostname discrepancy as unresolved until instance identity is read directly.
- Historical region was Phoenix (`us-phoenix-1`), availability domain 3, fault domain 2.
- Historical shape was `VM.Standard.A1.Flex`, Oracle Linux 8, AArch64, 2 OCPU and 12 GB RAM.
- The prior SSH account was `opc`. A Cloud Shell RSA identity was previously kept at `~/.ssh/cace_oci_runner_rsa`; its private key must never be copied into GitHub or printed. Historical notes also refer to a public IP and instance OCID, intentionally omitted from this public repository handoff.
- Earlier notes said OCI Run Command was RUNNING and that the Cloud Shell user was `morganaspi`; neither condition is confirmed now.
- Historical candidate runner roots included `/opt/actions-runner` and `/home/morganaspi/actions-runner`. Do not assume either exists.
- Historical notes described a runner service and watchdog with a 60-second heartbeat. Current service names, state, heartbeat, disk, and filesystem are unverified.

The only acceptable next action is a read-only, bounded inspection using a currently authenticated path. Never use the stale public IP/OCID or guessed hostname as sufficient identity. Verify the returned instance ID, hostname, architecture, and account before collecting any further metadata. The first remote reads should report filesystem free blocks/inodes and active runner jobs. If free disk is below an agreed safe threshold or cannot be measured, stop before recursive traversal. Keep file inventory metadata-only initially; do not copy runner files or cache contents into the VM, and do not read credentials.

## Expanded repository path inventory (exhaustive path match on inspected main trees)

A recursive Git tree query on the inspected `main` revisions returned the following OCI/runner/Avrea path matches. This is exhaustive for those repository tree snapshots, not for the VM filesystem.

### CACE OCI MCP source files
- `ops/oci_mcp/README.md`
- `ops/oci_mcp/__init__.py`
- `ops/oci_mcp/server.py`
- `ops/oci_mcp/policy.py`
- `ops/oci_mcp/cace-oci-mcp.service`
- `ops/oci_mcp/cace-oci-mcp.sudoers`
- `ops/oci_mcp/requirements.txt`
- `ops/oci_mcp/install.sh`
- `tests/test_oci_mcp_policy.py`

### CACE historical OCI/runner workflow archive
- `.github/workflow-archive/cace-oci-cleanup-a1.yml`
- `.github/workflow-archive/cace-oci-compute-probe.yml`
- `.github/workflow-archive/cace-oci-cutover-verify.yml`
- `.github/workflow-archive/cace-oci-formal-cache-prewarm.yml`
- `.github/workflow-archive/cace-oci-provision-durable-vm-v2.yml`
- `.github/workflow-archive/cace-oci-provision-durable-vm.yml`
- `.github/workflow-archive/cace-oci-register-cutover.yml`
- `.github/workflow-archive/cace-oci-runner-health.yml`
- `.github/workflow-archive/cace-oci-ssh-cutover.yml`
- `.github/workflow-archive/cace-oci-vm-start-inspect.yml`
- `.github/workflow-archive/cace-runner-diagnostics.yml`
- `.github/workflow-archive/cace-runner-persistence-probe.yml`
- `.github/workflow-archive/cace-runner-service-install.yml`
- `.github/workflow-archive/cace-runner-watchdog.yml`

### Expert Robot external runner workflows
- `.github/workflows/external-free-runner-bridge.yml`
- `.github/workflows/free-runner-capability-probe.yml`

The Expert Robot capability-probe workflow targets `avrea-ubuntu-latest-8-vcpu`, not the OCI runner. It requires a Railway SSH deploy-key secret, clones CACE into the Avrea runner's temporary directory, inspects CACE workflow metadata, and uploads a short-retention artifact. It has a `workflow_dispatch` trigger and deletes its own temporary work/evidence directories. Do not confuse this with OCI inventory, and do not dispatch it as an OCI substitute. Its presence does not prove Avrea availability or credential configuration.

### Inventory completeness statement

The GitHub source path inventory above is complete for the two inspected `main` tree snapshots at the time queried. The live OCI filesystem inventory remains **NOT_RUN / UNAVAILABLE**. No files from the VM have been read, copied, renamed, overwritten, or deleted.
