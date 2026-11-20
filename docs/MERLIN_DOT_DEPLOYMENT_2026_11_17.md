# Merlin production deployment checkpoint — 2026-11-17

## Result

The private engineering tool service is deployed on cace-oci-a1. It is a working subset of Merlin, not a claim that the full platform, autonomous RSI, direct ChatGPT MCP integration, native FreeCAD/ngspice, or independent CACE verification is complete.

- Service: merlin-dot-private.service; enabled and active; service UID982 (merlin-dot), group opc.
- Private AF_UNIX socket: /run/merlin-dot-private/tools.sock.
- PrivateNetwork=yes, NoNewPrivileges=yes, RestrictAddressFamilies=AF_UNIX; 384 MiB memory cap and one-core CPU quota.
- No public listener or new external account/API token.
- Runtime: Oracle Linux9.8/aarch64, Python3.9.25, two CPUs/10.64 GiB RAM; approximately97.55 GiB free at preflight.
- Package SHA256: 95e4985f5cf4af7b31bbb183047f6e2e4c4488034ec2d880e54f260feedb0b10.
- Release: /opt/merlin-dot-private/releases/95e4985f5cf4af7b31bbb183047f6e2e4c4488034ec2d880e54f260feedb0b10.
- State: /var/lib/merlin-dot-private/state. Only two synthetic engineering context records are seeded.

## Exact live evidence

| Check | Run | Result |
| --- | --- | --- |
| Host prerequisite inventory | https://github.com/morganaspim/Cace-app/actions/runs/44135882183 | SUCCESS; Python3.9/systemd/sudo/capacity |
| Runtime and socket/CLI tests | https://github.com/morganaspim/Cace-app/actions/runs/44137890841 | 83 tests passed, zero skips |
| Installation and live tools | https://github.com/morganaspim/Cace-app/actions/runs/44138569395 | SUCCESS; same83 tests rerun before installation; health/context/search/demo passed |
| Subsequent-job persistence and denied mutation | https://github.com/morganaspim/Cace-app/actions/runs/44139195492 | SUCCESS; same service PID1974176 remains active; job_submit rejected tool_not_allowed |

The runtime validation covers selected stdlib context, two-coder state, inbox, private transport and virtual-circuit contracts. It is not the full Expert Robot/CACE regression or mathematical qualification.

Installer review added13 passing local tests, including archive tamper/traversal/type/bounds checks, restrictive-umask behavior and hostile workspace/import-path isolation. Two coders independently reviewed each other's new runtime/simulation code.

GitHub artifact ZIP digests were independently checked:
- Deployment: 1febc662fb7c0e29f1b2555e9cef59de5ca1cdf72e6f84fa75c37ef296696d46.
- Subsequent persistence check: d3e74cf7037059b020f66cb84f62571da282be834008cbb1b842fc98cf8699c9.

One deployment attempt (44138280347) stopped before installation because its token lacked Actions read permission for the exact validation-run lookup. The workflow was corrected to contents:read/actions:read, retaining the validation gate; the later deployment succeeded. No source/cache cleanup or existing CACE service replacement was performed.

## Working tools and invocation route

Fixed GitHub-mediated operations on CACE branch merlin/dot-ops/production-20261117 accept exactly one additive request file at merlin/dot-requests/<uuid>.json. The push-triggered workflow is .github/workflows/merlin-dot-oci-operations.yml.

The inspect profile checks the running service without installation or package changes. The tool_call profile accepts only health, context_status, context_search, context_fetch and virtual_circuit_demo with bounded JSON arguments. Peer LinuxUID1000 is granted only reviewed reads/simulation. It is not an authenticated GitHub workflow identity.

Example request (generate a NEW UUID and current timestamp; do not replay an old deployment):
{
  "schema": "merlin-dot-ops-request-v1",
  "request_id": "<new UUID>",
  "operation": "tool_call",
  "created_at": "<current timezone-aware timestamp>",
  "tool": "virtual_circuit_demo",
  "arguments": {}
}

Do not invoke deploy again: the additive installer refuses existing paths/identity rather than overwriting an installation. Read the current fixed workflow and source hashes before later operations.

This is indirect access through GitHub to a Unix-socket service, not a connected remote ChatGPT MCP server. Root installer and tool clients use isolated or pinned import paths. No SSH key from chat was used.

## Virtual engineering result

The fixed ideal5V DC experiment uses Merlin's canonical Engineering IR to compare1k/1k and9k/9k resistor pairs. Both yield2.5V unloaded; modeled resistor dissipation changes from1/80W to1/720W (ninefold reduction). KCL and power-balance residuals are exact zero within the rational ideal model. Higher source impedance/load sensitivity and physical tolerances remain outside that conclusion.

The result includes wiring, SPICE text and OpenSCAD preview exports. It is simulated, not physical safety certification, fabrication approval, independent CACE evidence or formal proof. No automatic candidate adoption or promotion is enabled. Native FreeCAD and ngspice were absent and were not installed.

The selected Drive torus OBJ was inspected as inert data:257799bytes, SHA256233ddd6f8945daed900752b04fd8da263ee7bacda497e43ced6b1f4fe021c8ee,1568vertices/4704edges/3136faces, Euler characteristic0, every edge incident to two faces. Units are undeclared; these checks do not prove solid validity or physical suitability. Native FCStd/STEP/STL/FCMacro search returned zero in the searched accessible scope. A Drive modeler source contains syntax errors and constant/placeholder routines; its ideas are preserved, not deployed.

## Context and idea coverage

The plan preserves191 exact-source Expert Robot docs/configs; all source bytes were captured and matched Git blob hashes. Four master documents were semantically read fully in this planning pass;187 remain individually queued. Metadata enumeration covered283 accessible Drive documents;134 unique relevant project assets were retained, including36 known Merlin-folder items. The plan also preserves100 PR snapshots,30 chat-origin idea statements,10 ranked tracks and37 unassigned tasks.

The pre-existing source-preserving project context set has41 records/23 distinct text snapshots from accessible chat handoffs and project files. It is not every account chat or every raw transcript. Neither metadata indexing nor capturing bytes is complete semantic review.

Automatic review rejected copying the full private191-document corpus into the separate CACE repository. The accepted safer package contains only necessary runtime code/tests plus two synthetic records. Raw chats/full private corpus/Drive exports were not copied to CACE or seeded on its shared runner. The full captured corpus remains with the existing project context and source repository.

## Reviewable repository changes

- Expert Robot draft PR178: https://github.com/Mannyspiro/expert-robot/pull/178 .
- Expert Robot application/coverage source commit: fed29f3c0ff22751f327fc94895ecdb640324594 .
- CACE draft PR116: https://github.com/morganaspim/Cace-app/pull/116 .
- CACE verified inspection request commit: eae8fab1fccc146850e84f2835a53041a620e0e1 .
- Plan: docs/MERLIN_PRODUCTION_COVERAGE_PLAN_2026_11_17.md .
- Machine-readable coverage: config/merlin/dot-production-coverage-20261117.json .

Both PRs are stacked on existing feature branches. No merge or bulk integration of unrelated PR ancestors was performed. The service source package matches the new private runtime/simulation files by content hashes; the manifest separately records the older canonical source base703b21e3639c239484e851bebdb1a60c755d4924.

## Best next production steps

1. Finish deterministic review and source/version reconciliation of the queued docs and selected Drive archives; retain every useful idea in canonical catalogs. Add retrieval-quality evaluation before broad ingestion. Keep raw private chat access separate from the shared runner UID.
2. Complete real caller identity/private dot registration and least-privilege context publication. The local service works without credentials; a direct remote MCP connection is not provisioned.
3. Wire actual two-coder providers and an independent held-out evaluator into Hermes/MCFC with OS-enforced budgets, cancellation, durable recovery and exact ArtifactRefs. Interactive coding agents used here are not deployed autonomous provider adapters.
4. Complete independently authenticated CACE artifact/qualification receipts and trust custody. Do not equate test/run hashes with independent verification.
5. Qualify native headless FreeCAD and ngspice on an appropriate existing free runner, then test a single versioned CAD/frame/netlist/simulation round trip. Check geometry units, constraints and declared assumptions.
6. Connect the real research/evidence events to the HUD, voice and learning workflow; benchmark model/context optimization only after a measured baseline. Preserve advanced Xenomaths/ideonomy/science proposals as research.

Capability can grow through measured improvements; signing, execution and promotion authorities remain separately controlled.
