# Proposed isolated OCI security-monitoring acceptance profile

Date: 2026-11-24. Monitoring-profile execution status: **proposed, not approved, not installed, not dispatched**.
Proposed profile identity: `wilborn_security_monitoring_synthetic_v1`.

The request, fixed-manifest and minimized-preflight contract is implemented in
`wilborn_ops/security_monitoring_profile.py`. It cannot execute acceptance stages.
The execution adapter, reviewed runtime and installed profile remain open.

This document specifies one reviewable synthetic acceptance job. It grants no
runner authority, installs no gateway operation and authorizes no deployment.
The host and existing services remain unchanged. The job may mutate only its
disposable synthetic fixtures, including activating a fixture successor to test
handover; it must never activate a production writer or monitoring service.

## Existing route and exact source review: proposal baseline

At proposal preparation, read-only verification found the operations branch
`merlin/browser-operations-20261121` at
`3e772229d5effed851c8c666da9127a441e0b2ff`. Its
[fixed gateway](https://github.com/morganaspim/Cace-app/blob/3e772229d5effed851c8c666da9127a441e0b2ff/.github/workflows/merlin-oci-job-gateway.yml)
allows seven named inventory, MCP, CACE, RSI and C++ operations. None is a
Wilborn security-monitoring acceptance profile. The existing three-minute
gateway budget, source allowlists and no-package-installation policy must not
be repurposed or broadened by submitting this proposal as a request.

The following are provenance parents, **not executable candidate pins**:

| Component | Reviewed parent identity | Candidate requirement |
|---|---|---|
| Producer, PR #228 | `e619f14b0ac0b1439065bb99a7ea41ae52c95f7f` | Published handover candidate commit, complete Git tree and reviewed dependency/test inventory are pending. |
| Studio, PR #229 | `315fccb5bd3103b1400c07715d489e239818a4b9` | Exact compatible published Studio commit and its producer pin must be reconciled to the chosen producer candidate. |
| Studio package | Parent source-only ZIP SHA-256 `62327585e33464bfff0b72a4f0e8d65d15e4300fb84a2697de03c01517d92dac` | Candidate package bytes, SHA-256, exact manifest and source relation must be reviewed; the parent digest is not a candidate acceptance value. |
| OCI execution wrapper | Non-dispatching contract implemented; no execution adapter approved | Exact reviewed wrapper, isolation configuration and runtime image identities are required before installation or execution. |

An absent candidate identity blocks execution. Resolve each candidate to a
full immutable commit, not a branch, tag, pull-request merge ref or latest
artifact name. Compare the complete reviewed tree and manifest; a Git commit
label alone does not establish unchanged local files. Preserve canonical
`ArtifactRef` and existing project evidence references where available, without
creating another source-of-truth registry. Record all source and dependency
identities in the minimized result.

## Implemented non-dispatching contract

The fixed manifest now records this reconciled acceptance baseline separately
from the historical proposal parents:

| Input | Expected identity; not a live acquisition claim |
|---|---|
| Producer commit / tree | `33303d5947024d10155a66a6dc6d46221088276a` / `d76d66364e2f77b8ff1a043d4edf4c58ff64a65a` |
| Studio commit / tree | `0202024ea3e98d5d64e4f158babcee287e2a8eef` / `43af8844d996ca10e4b9a7894767ac7594bb6365` |
| Source-only Studio ZIP | SHA-256 `9d179b5f52f9e7ee72b7bf88f024f5480d8d4c4902c547c8e78c6525ebf7d520`; 100,572 bytes |
| Producer test-file inventory | 43 files; SHA-256 `ee28ba4940b1f72531571654af82d51e3d89957fd89c490acc4c891a0af284fa` |

The inventory is the union of `tests/test_wilborn_*.py` and
`tests/test_cace_attestation.py` at the pinned producer commit, sorted by path.
Each entry contains `path`, byte count as `bytes`, and file `sha256`; hash the
UTF-8 JSON array with sorted object keys and compact separators. This binds
file contents, not a claim that every test has run or that case coverage has
been reviewed for the future runtime. The new contract tests are wrapper tests
and are outside that frozen producer baseline. A later acceptance candidate
requires deliberate reconciliation of its source tree, file and case inventories,
Studio producer pin and package; do not silently substitute the branch tip.

The command reads at most 4,096 request bytes from standard input. It accepts
exactly `schema`, `request_id`, `profile_id`, `reason` and `created_at`.
Request IDs must be canonical UUIDs, reasons must be 1–300 printable characters,
and timestamps must be valid UTC `YYYY-MM-DDTHH:MM:SSZ` values. It rejects duplicate
JSON keys, malformed or excessively nested JSON, nonfinite numbers, unknown
fields and every attempt to provide execution or runtime configuration.

Inspect the fixed review manifest:

```sh
python -I -B scripts/merlin/wilborn_security_profile_preflight.py --describe
```

Submit a synthetic preflight request:

```sh
python -I -B scripts/merlin/wilborn_security_profile_preflight.py <<'JSON'
{"schema":"wilborn-security-monitoring-request/1","request_id":"63d3ba1a-27c1-4e50-a8fd-5ee2c69e507b","profile_id":"wilborn_security_monitoring_synthetic_v1","reason":"Review synthetic acceptance prerequisites","created_at":"2026-11-24T12:00:00Z"}
JSON
```

Exit status **3** means the request is valid but acceptance is blocked; it does
not mean tests passed. Exit **2** rejects the request, and **0** is reserved for
describing the manifest or help. There is no execute, install, runtime-override,
source-override or dispatch option. The CLI does not inspect the host, access
the network, read candidate input paths, import acceptance workloads or write
files. `-I -B` isolates Python startup from caller import paths and disables
bytecode writes; the entry point locates its own trusted repository source.

This contract version always reports `BLOCKED_DEPENDENCY_REVIEW` and
`BLOCKED_PROFILE_NOT_PROVISIONED`: no reviewed runtime or installed-profile
identity is configured. Those statuses describe absent prerequisites in the
reviewed configuration, not a fresh inspection of an OCI host. Runtime and
installation digests remain null. The first stage is `BLOCKED`; all subsequent
acceptance stages are `NOT_RUN`. Acceptance test count is zero, resource
measurements are null, and every execution, production, deployment and custody
authority flag is false. The expected public source identities are clearly
separated from verification flags, which remain false.

Receipts use `wilborn-security-monitoring-preflight/1`, bind the canonical
request and fixed manifest by SHA-256, and are capped at 64 KiB. Audit reason
and timestamp text are hashed rather than echoed. The strict blocked-only
validator rejects extra fields, logs, host metadata, invented measurements,
changed identities, passed-stage claims and false-to-zero type substitutions.
This receipt schema cannot stand in for the future execution evidence schema.

Optional Python-API reconciliation accepts an exact existing `ArtifactRef`
through `MerlinRegistry.read_artifact_ref`, restricted to project `wilborn-demo`
and `security/monitoring/preflight/<request-id>.json`. The canonical reader now
checks both immutable registered size and actual opened-file size before any
blob content read or hash. Registry metadata must include the corresponding
artifact row, its digest-derived canonical storage path and matching size;
orphaned or inconsistent metadata fails before opening a blob. It uses one
regular-file descriptor and an unbuffered
read of at most 64 KiB plus one overflow-detection byte; oversized content is
never hashed. It validates the exact retained bytes, digest, size and unchanged
descriptor state before returning them, then validates the complete
request/profile binding. This is a logical blob-read bound, not a measurement
of physical disk IO or a limit on SQLite metadata inspection. Missing, corrupt or
conflicting evidence fails instead of rerunning. It performs no latest-version
lookup, registry write, retry or automatic scheduling. An authorized host may
retain returned bytes using the existing registry; no second registry is added.
The CLI exposes no registry path or reference input.

Contract tests live in `tests/test_wilborn_security_monitoring_profile.py`.
They exercise request and receipt attacks, exact-version replay, corrupt blobs,
hostile working directories/import paths and the blocked CLI exit. These are
local contract tests, not kernel-isolation or OCI acceptance evidence.

Independent review reproduced an inherited registry defect: the former bounded
read first called the public resolver, which hashed an entire oversized blob
before checking its requested byte limit. The canonical reader was repaired;
the explicit public `resolve_artifact_ref` and `verify_artifact` operations
retain complete-artifact verification for valid inputs. Resolution now also
rejects corrupt catalogue paths or inconsistent catalogue/version sizes;
normal valid-artifact results and provenance are preserved. Negative tests cover an
oversized registered blob, a blob grown beyond its registered size, growth after
the descriptor-size check, within-bound corruption, nonregular files and cleanup
after read failures. Monitoring replay also has a direct no-full-read/no-full-hash
regression. This is one repair to the shared registry, not another storage layer.

## Fixed request boundary

After separate profile review and installation, the only request-specific
input would be an opaque request ID and bounded audit metadata. Select the
installed reviewed profile version by its fixed identity. Executable source,
package, runtime, test inventory, resource limits, output schema and paths
belong to the profile, not the request. Reconcile duplicate request IDs to the
existing result before deciding whether any retry is appropriate.

Reject unknown fields and any caller-supplied command, shell fragment, Python
code, URL, source override, path, environment variable, network target,
credential, secret, signing key or alternate test selector. The wrapper uses
fixed argument arrays and runner-created locations. The CLI paths used by
existing test entry points are populated only from those verified locations;
they are not exposed as request parameters. No job may enable another OCI
profile or dispatch a second workload.

## Isolation and runtime prerequisites

Use a separately reviewed nonprivileged, disposable execution boundary with
kernel-enforced process, memory, CPU, storage and network limits. A temporary
directory or an application-level timeout alone is insufficient isolation.
Mount verified producer and Studio sources and the verified package read-only.
Provide a new owner-only scratch directory and private temporary/home
directories. Disable bytecode writes into source checkouts.

Do not expose production directories, host credentials, signing services,
rollback-anchor stores, live databases, model workspaces, service-control
sockets, localhost MCP endpoints, container-engine sockets or inherited file
descriptors. The execution process receives no GitHub token, cloud credential
or general host environment. Read-only host access does not mean permission
to read private host files: only reviewed input mounts are visible.

Network access is denied inside the job. Permit the fixture Studio client and
server to use loopback within the isolated boundary only; do not expose a host
listener or contact a host service. A trusted outer acquisition step may fetch
the exact public sources and package through the already approved mechanism,
verify them, then hand over bytes without passing its credentials or network
capability to the test process. Failed acquisition is a distinct blocked stage.

Use a preprovisioned, reviewed Python 3.11 runtime with an exact patch/build,
Linux ARM64 image digest, SQLite build and `cryptography==50.0.2` binary-wheel
digest recorded in its manifest. The version matches the current development
fixture dependency; compatibility on the eventual OCI image is unmeasured.
The profile must verify those identities before importing candidate code.
An absent or incompatible dependency is `BLOCKED_DEPENDENCY_REVIEW`; it is
not permission to run pip, install a compiler, fetch a wheel, change a cache or
fall back to another cryptographic implementation on the shared host.

## Fixed acceptance stages

These are entry-point specifications for the future wrapper, not a runnable
gateway change. Paths are relative to its source-pinned, read-only inputs.

| Stage | Fixed entry point or check | Required result |
|---|---|---|
| Identity and isolation | Wrapper-owned manifest, source-tree, runtime and effective isolation checks | Exact reviewed inputs; isolated nonroot process; required limits active; no production capability exposed. |
| Producer regressions | `python -m unittest discover -s tests -p 'test_wilborn_*.py'` in the producer checkout | All reviewed tests execute with zero failures, errors or unexpected skips. The resolved inventory must include the handover, generation, lineage and per-write custody tests, including every reviewed process-crash test. |
| Canonical signature boundary | `python -m unittest discover -s tests -p 'test_cace_attestation.py'` in the producer checkout | Existing verifier negative and positive controls pass on the same runtime. |
| Full-capacity recovery and repeated handover | `python tests/wilborn_security_recovery_workload.py` with only wrapper-owned import paths | Require workload schema v3. Reach 1,023 signed events/revision 1,024; reject event and review overflow; preserve exact encrypted history, archive bytes and pending alerts. Complete two separately reviewed transfers and reopened ownership, yielding three segments with 1,023 / 2 / 2 events (1,027 total), final epoch two and active segment index two. Reject stale objects and the retired previous active writer; verify the complete lineage before returning the final 20 incidents. |
| Producer-to-package display | `python portable/tests/security_handoff_smoke.py --producer <verified-producer> --package <verified-package>` in the exact Studio source | Verify the source-only ZIP inventory and hashes. Actual v1, staged v2 and active-lineage v3 exports must each reach the extracted-package loopback page in separate processes; cross-origin rejection and immutable startup snapshot checks pass. The v3 page labels verification as host-reported and grants no execution or deployment authority. |
| Preservation and termination | Wrapper-owned postflight | Input identities unchanged; no remaining child processes/listeners; bounded result emitted; only disposable state removed. |

The handover test inventory requires real separate-process interruption and
restart, in addition to in-process exception injection. It must demonstrate
predecessor fencing before successor writes, stale and unleased writer
rejection through event and operator-review paths, exact compare-and-swap
ownership, no duplicate sequence allocation, rejected concurrent stale
takeover, and restart after each persisted transition boundary. Competing
writers must leave at most one accepted current ownership token. Test failures
must preserve the last valid history and unresolved predecessor alerts.
Continuation must permanently retire the old coordinator without rewriting
its original enrollment or grant. Competing child branches must have exactly
one accepted retirement destination; a retired coordinator must not return to
preparation, activation or ownership acquisition. Real process interruptions
must cover successor enrollment, parent retirement and ledger commit boundaries.
The declared bound is seven transfers/eight segments: the eighth segment must
remain usable and exportable, while an attempted ninth fails before retiring
the current owner. Missing, reordered, cyclic or damaged ancestry must block
recovery and active-lineage export, including a zero-entry display window.

Every enrolled event or operator-review mutation must reread and verify its
currently retained custody receipt before invoking the signer and hold that
receipt stable through commit. Exercise an already-open writer against an
expired or unavailable receipt and against a rollback behind a newly retained
anchor. A current retained anchor may lag the live tip; this check must not be
described as an independent external anchor being created for every event.
Frozen predecessor tips and their archives still require exact matching anchors.
Failure injection may terminate only fixture-owned processes inside the job;
host reboot and existing service interruption are excluded.

Source review must confirm these cases are actually present and discriminating
before pinning the test inventory. A passing suite name or count is not a
substitute. The staged v2 viewer remains explicitly non-authorizing and does
not report active handover merely because the separate handover tests pass.
The v3 1,023-event workload extends the earlier v2 experiment with another
reviewed transfer, third-segment writes and complete active-lineage export.
The historical v2 experiment remains earlier evidence, not the current
acceptance target. Neither workload itself injects abrupt process termination;
that evidence comes from the separate handover and generation process tests.

## Proposed budgets and stopping rules

These are conservative **review proposals, not measured OCI capacity or a
production SLA**. The existing full-capacity workload already enforces a
210-second ingestion check, a 230-second overall internal check and a 64 MiB
database bound; its CI wrapper uses a 240-second outer deadline. Preserve those
checks without enlarging them to obtain a pass.

| Resource | Proposed fixed maximum | Reason and enforcement requirement |
|---|---|---|
| CPU | Two logical CPUs, 600 aggregate CPU-seconds per job | Bounds interference and runaway computation; enforce outside candidate code. Actual ARM64 sufficiency remains to be measured. |
| Memory | 1 GiB for the complete process group | Allows Python, crypto and bounded process fixtures; a proposal with no measured peak-memory claim. Kill the job on breach. |
| Processes | 64 within the isolated job | Allows bounded concurrency/crash fixtures while bounding process creation. Child processes remain in the same limit. |
| Scratch | 512 MiB total; existing 64 MiB per-workload database cap retained | Covers temporary ledgers, archives and package extraction; enforce a real quota, not a post-run size check alone. |
| Total wall time | 720 seconds | Budgets below total 630 seconds, leaving 90 seconds for bounded orchestration. A timeout is a failed result, not a reason for an automatic larger retry. |
| Stage wall time | Identity 30 s; producer tests 180 s; verifier 30 s; workload 240 s; package handoff 120 s; preservation/cleanup 30 s | Wrapper supervises each process group; existing tighter child deadlines stay in force. |
| Export | One strict JSON receipt, at most 64 KiB | Numerical evidence and test outcome identifiers only. Reject schema extras and excessive output. |

Stop on an identity mismatch, failed isolation prerequisite, invalid fixture
signature, preservation failure, resource breach or failed required test.
Mark remaining stages `NOT_RUN`; retain the failed stage and termination
reason. The supervisor must terminate every child on a deadline and confirm
that no fixture listener remains. Review failed/null measurements before any
revision of budgets or test selection; do not silently retry with new values.

## Minimized evidence contract

Return profile version and wrapper/runtime/source/package digests, request ID,
test inventory digest, per-stage passed/failed/blocked/not-run counts, elapsed
time and actual resource measurements where measured. Include the workload's
bounded numerical fields and explicit invariant outcomes for fencing,
compare-and-swap, process-crash recovery, preserved history, overflow rejection,
archive preservation and package display. Label measurements by architecture,
runtime and exact candidate identity. Do not aggregate overlapping targeted
and full-suite counts as unique tests.

Output `data_class=synthetic`, `production_qualified=false`,
`deployment_authorized=false`, `operational_custody_verified=false` and
`production_writer_activated=false`. A successful job may describe a tested
fixture ownership transition; it cannot issue a production lease or sign a
release statement. Exclude private key material, signatures/anchor receipts,
raw event or incident payloads, database copies, tokens, environment dumps,
host inventory and unrestricted stdout/stderr. The wrapper converts failures
to reviewed stage/test IDs and bounded error classes. Do not upload raw logs
through a second artifact path.

## Operational custody and release remain separate gates

All execution fixtures use newly generated ephemeral test keys under the
isolated job. They exercise actual signature and encryption code but establish
no independently administered trust. Production requires separately
provisioned Titan encryption/signing custody, distinct authorized operator and
reviewer identities, a current independently retained rollback anchor, and
recovery policies that cannot restore a stale writer fence or grant together
with an older ledger. The actual OS ownership, storage durability and custody
failure domains must be reviewed on the intended private host.

The local handover contract assumes a trusted single host and its documented
SQLite/process-lock behavior. It is not distributed consensus or evidence of
power-loss behavior on untested storage. Private-host acceptance must exercise
the deployed authentication, process ownership, fenced restart, backup and
restore paths. No synthetic OCI result closes those operational requirements.

The release gate also requires the new signed `durable_writer_handover`
statement, independently pinned and bound to the exact release artifact and
source. This proposed job emits development evidence for review, not that
statement. Existing native CI and other release gates retain their own source
and scope; this Python monitoring profile does not replace them.

## Readiness record

| Gate | Current status | Required next evidence |
|---|---|---|
| Candidate source/package/runtime pins | Pending | Published immutable identities, reviewed inventory and exact compatibility reconciliation. |
| Fixed contract and preflight | Implemented; non-dispatching and blocked-only | Exact request/manifest/receipt checks and existing-registry replay have local tests; no execution or isolation qualification follows. |
| Execution wrapper and isolation implementation | Not implemented or approved | Reviewed execution adapter/configuration and independently inspected effective isolation remain required. |
| Profile installation and execution authority | Not approved | Recorded approval for this exact fixed profile and isolated host route; no inference from existing seven operations. |
| Existing inventory route | Executed successfully on 2026-11-24 | The observation below establishes availability during that job; it does not install or qualify the proposed monitoring profile. |
| Actual OCI acceptance | Not run | Source-bound minimized receipt from the approved isolated run, including failed or blocked stages. |
| Operational key/anchor custody | Not established | Actual independently administered provisioning and verified current recovery anchor. |
| Private-host qualification and release | Open | Actual deployment-environment acceptance and separate authorized release decision. |

Canonical traceability: master plan v6
`MERLIN-PRODUCTION-MASTER-20261117` at
`6d4b5a4a3a5b81210d192554774316c04d2d88ff`, tasks `P00-3`, `P00-4`,
`P02-3`, `P04-3`, `P04-4`; gates `G-SOURCE`, `G-SCOPE`, `G-EVIDENCE`,
`G-RECOVERY`, `G-PROMOTION`. Append actual identities and results in the existing
parent-linked plan history. Do not replace historical measurements or mark
these operational tasks complete from this proposal.

## Appended observation: actual OCI availability

The existing fixed read-only inventory operation completed successfully in
[run 45392435551](https://github.com/morganaspim/Cace-app/actions/runs/45392435551).
The matching job establishes assignment and execution during that observation.
Its result explicitly leaves qualification false. Detailed operational
inventory and the original receipt are retained separately from this public
proposal.

This result does not establish continuous availability, effective isolation,
exact runtime compatibility or Wilborn acceptance. No monitoring profile was
installed or dispatched. The wrapper, runtime review, independent custody and
private-host requirements above remain open.
