# Merlin Status, Decisions, Dependencies and Roadmap

**Snapshot:** 2026-11-16  
**Companion:** [MERLIN_MASTER_CONTEXT.md](./MERLIN_MASTER_CONTEXT.md)

## 1. Decision ledger

| Decision / constraint | Current interpretation |
|---|---|
| MVP first | Prioritize a trustworthy source-to-verified-artifact research loop before broad agentic features. |
| Autonomous continuation | Perform routine repository and analysis work directly where authorized; do not offload routine steps to the user. |
| Skeptical science | Hermes decomposes/teaches; Logos challenges; CACE independently verifies. |
| Capability vs authority | Capability may improve; authority never expands automatically. |
| Public sources | Use publicly available sources and public-domain/open materials subject to license. |
| Preserve originals | Derived artifacts never replace/delete source artifacts; retain append-only lineage. |
| Canonical architecture | One registry, universal ArtifactRef, knowledge graph, evidence bridge, event/outbox and worker fabric. |
| Virtual GitHub | Internal/headless Git-like workflow is primary; GitHub is a read-only/optional external adapter. |
| Fail closed | Missing CACE transport, provenance, supervisor or capability qualification means unavailable/unqualified, not assumed success. |
| Compute | No paid compute; avoid speculative CI. Avrea unavailable until 2026-12-01; preserve its reported 3,000-minute budget. |
| Cloudflare | Removed/disabled; do not build around Cloudflare unless user changes decision. |
| Titan | Separate security/encryption research track; do not merge into experimental invention graph. |
| Production authority | No merge, deploy, signing, trust-root change, production secret mutation or capability promotion without explicit authorization and gates. |

## 2. Current implementation snapshot

### Repository baseline
- Main application repository: `Mannyspiro/expert-robot` (private).
- Default branch observed on 2026-11-16: `main`.
- Existing README describes Python orchestration and a C++ trusted/performance runtime, with cognition, imagination, research, skills, swarm, model server, tool execution, sandbox, benchmark and telemetry subsystems.
- This README is repository baseline context; it does not prove all listed subsystems are complete or integrated with newer Python Merlin services.

### Ideonomy/Hermes/Logos
- PR #171: enumeration; source binding and candidate identity corrections recorded, exact-head CI not passed/verified.
- PR #172: Hermes stage with runtime-owned generator provenance and SQLite replay journal; tests authored, exact-head run not recorded.
- PR #175: immutable generator provenance; tests authored, exact-head run not recorded.
- PR #176: Logos skeptical review; validator, lineage checks, review artifact/graph edge, journal replay and tests authored; tests not executed. Opening PR automatically queued unified-platform and CI runs at head `895d8418aae8471c32fca81e09631139d1e31bbb`; last observed unified-platform queued and CI pending. Recheck current state.
- No CACE verification or production qualification of these new stages has been established.

### Media
- PR #173 inventory and PR #174 adapters exist in prior status ledger.
- PR #174 build-and-smoke CI reported successful at its exact recorded head, optional inference skipped.
- Runtime launch/qualification is blocked by missing OS sandbox, bounded streaming, environment allowlisting and process-tree enforcement.
- Blender/ComfyUI archives are source/toolchain inputs, not proof of an installed or running environment; no ComfyUI model weights were included.

### RP² formalization
- PR #102 in `morganaspim/Cace-app` defines chain-complex structures and partial properties.
- Desired integral homology classifications and exact pinned Lean compile are still outstanding.
- Independent Python calculation is a reference, not formal proof.

## 3. Historical infrastructure notes

- Reported local compute: 8 vCPU, about 24.8 GB available cache/current available memory (historical).
- Avrea: reported 3,000 runner minutes remaining; unavailable until 2026-12-01 by explicit user instruction.
- OCI: previously identified `cace-oci-a1`, ARM64, persistent Lean/mathlib cache and least-privilege instance-principal access. Verify before use.
- OCI ARM64 cannot directly execute the supplied Blender Linux x86-64 binary.
- Avoid reusing the previously mentioned unrestricted `ocarun` sudo setup.
- No Google Drive transfer is available because connector disabled by admin. Do not claim transfer.
- No combined backup ZIP currently verified in the active runtime; earlier packaging attempt failed due rate limiting. Do not retry or claim a new archive unless separately requested.
- Do not delete Library items or originals based on assumptions about Drive/project membership.

## 4. Critical dependency graph

```text
Canonical Registry + ArtifactRef
          |
          v
Source Intake / Extraction -----> Source Provenance
          |
          v
Ideonomy Enumeration
          |
          v
Hermes Stage Journal / Outbox
          |
          v
Logos Skeptical Review
          |
          +------> Numerical / Counterexample / Lean / Literature / CAD Experiments
          |                          |
          +--------------------------+
                                     v
                        Independent CACE Verification
                                     |
                                     v
                         Canonical Evidence + Graph
                                     |
                                     v
                        Research Synthesis / Learning
```

Cross-cutting requirements: MCFC process supervisor, capability registry, security policy, telemetry, immutable provenance, explicit approvals and exact artifact identity.

## 5. Ranked next actions

### Priority 0 — Establish a trustworthy end-to-end research path
1. Recheck current PR heads and workflow states for #171, #172, #175 and #176.
2. Add end-to-end Hermes → Ideonomy → Logos tests using canonical registry artifacts, not isolated validator-only tests.
3. Test replay after projection failure and completed replay; test same idempotency key with altered input; document provider in-flight crash limitations.
4. Add exact source-locator tests that prove each candidate and each quotation maps to the underlying extraction manifest.
5. Integrate CACE using a real authenticated transport. If unavailable, keep the stage result unverified and capability unqualified.
6. Add explicit stage orchestration and outbox acknowledgement tests.

### Priority 1 — Worker supervisor and security
1. Specify MCFC supervisor contract and actual OS/container enforcement.
2. Implement wall-clock deadline, CPU/memory limits, process-tree termination, cancellation, workspace isolation, restricted network/filesystem and secret isolation.
3. Enforce concurrency leases and handle lease expiry with worker termination/fencing.
4. Test failure races, noisy output, oversized inputs/outputs and partial cleanup.
5. Ensure provider provenance is authenticated or explicitly marked as runtime declaration.

### Priority 2 — Math discovery and formal proof
1. Complete equation atlas source normalization and entries 021–100.
2. Build a single evidence-backed Math Discovery Engine pipeline.
3. Finish RP² H0/H2/H1 proof decomposition in Lean; pin toolchain and compile exact source.
4. Add reproducible numerical and counterexample receipts.
5. Connect Lean/numerical outputs to CACE exact-digest verification.

### Priority 3 — Engineering and virtual lab
1. FreeCAD importer and engineering IR.
2. CAD assemblies and wiring/netlist graph.
3. Safety, thermal and manufacturability checks.
4. ngspice with exact version/input/output/resource receipts.
5. MCFC virtual lab and reproducible experiment lifecycle.

### Priority 4 — Media runtime
1. Harden Blender and ComfyUI adapters with bounded streaming, allowlisted environment and external sandbox.
2. Ensure Linux architecture compatibility and pinned binary/source revisions.
3. Verify model/workflow licenses, hashes and versions.
4. Run minimal isolated acceptance tests only after supervisor gates.
5. Promote media capability only after independent evidence.

### Priority 5 — Product and self-improvement
1. Unified HUD for jobs, agents, evidence, resources and approvals.
2. Research canvas and evidence-flow visualization.
3. Internal virtual Git/PR/CI lifecycle.
4. Adaptive learning paths and Math Kung Fu.
5. Held-out provider evaluation and controlled self-improvement lifecycle.

## 6. CI and resource discipline

- Do not start workflows merely to see what happens.
- Prefer local/static checks when available and safe.
- Before any Actions run, identify the exact commit, acceptance criterion, expected jobs, compute budget and owner-approved window.
- Check for existing runs first; do not create overlapping runs.
- Report queued, in-progress, skipped, cancelled, failed and successful states accurately.
- CI success proves only what that workflow tested at that exact head.
- Avrea is unavailable until 2026-12-01; do not consume its reserved minutes.
- Do not run a real media worker or untrusted workflow until OS-level isolation exists.

## 7. Status vocabulary

Use these terms consistently:
- **Planned:** design or requirement only.
- **Source-authored:** code/documentation committed, not necessarily executed.
- **Test-authored:** tests exist, not necessarily executed.
- **Locally tested:** tests actually executed in a named environment.
- **CI-tested:** exact commit was tested by named workflow/run.
- **Runtime-demonstrated:** actual service/worker executed under stated conditions.
- **Independently verified:** exact artifact verified by CACE or another explicitly accepted independent verifier.
- **Qualified:** all capability-specific gates and approvals satisfied.
- **Promoted:** explicit authorized change to production capability state.

Never skip levels by implication.

## 8. Change log

- **2026-11-16:** Created cross-chat master context, research atlas and status/roadmap documents from the available saved context, recent project handoffs and current repository inspection. Includes explicit implementation-vs-plan distinctions and historical status caveats.
