# Exact OCI build evidence admission

## Scope and defect

The existing v2 build gate requires the observed publication branch head to equal
the tested source commit. A branch can legitimately advance with a checkpoint or
proposal while every selected source file remains identical. Replacing the
observed head with the tested commit would misstate the evidence. Separately, the
v2 decision API has no context-case gate or concrete importer for the existing
OCI archive and provider run metadata.

The v3 path records both commits and compares both complete selected manifests:
path membership, SHA-256 file hashes, Git blob identities, selected-file count,
and recomputed source-map digest. Its relation is `same_commit` or
`identical_selected_files`. It explicitly does **not** claim whole-commit
equivalence, ancestry, or validation of files outside the selected shard.

`BuildGoal`, `decide_build`, and `record_build_decision` retain the v2 schema and
branch-equality behavior. Opting into the new API requires `BuildGoalV3` and an
`OCIAdmissionPolicy`; there is no silent upgrade or fallback to v2.

## Host entry points

`merlin.build_admission.admit_oci_build` is the reusable host entry point. The
caller supplies an existing `MerlinRegistry`, an existing project, a frozen v3
goal, exact policy pins, ten existing `ArtifactRef` values, and a provisioned
authentication callback. The callback receives `(role, detached_ref,
byte_sha256)` and must return literal Boolean `True` for that exact observation.
There is no default authenticator, signer, credential, network fetcher, provider
invocation, or production identity provisioned by this module.

The host must establish provenance independently: which provider/repository/run
supplied bytes, which commit was observed, which selected files were read back,
and whether the callback is permitted to authenticate those specific artifacts.
Registry integrity checks and matching hashes establish byte identity; they do
not establish that the runner or the host's claims are trustworthy.

| Evidence role | Required original or host-owned content |
| --- | --- |
| `run` | Exact retained GitHub run JSON, including repository, ID, attempt, workflow path, branch, commit, terminal status and conclusion |
| `artifact_metadata` | Exact retained GitHub artifact-list JSON, with the selected artifact ID, attempt-bound name, size, SHA-256 and workflow-run binding |
| `archive` | Exact selected Actions artifact ZIP bytes |
| `report` | Original `report.json` bytes with `merlin-egm-oci-validation/2` |
| `controller_identity` | Original `controller-identity.json` bytes |
| `controller` | Original archived `controller.txt` bytes |
| `workflow` | Exact workflow bytes at the policy's workflow commit; independently authenticated by the host |
| `tested_manifest` | Original archived `source-manifest.json` bytes with `merlin-egm-source/2` |
| `published_manifest` | Canonical host observation of the same complete selection at the actual observed publication head |
| `publication` | Canonical host observation binding the repository/branch/head, tested commit/map, and both exact manifest references |

Original native/provider JSON need not be reserialized. Duplicate keys, invalid
UTF-8 and non-finite numbers are rejected. Host envelopes use the repository's
canonical JSON encoding. All references must belong to the same project.

The published manifest schema is `merlin-published-source/1`, with `repository`,
`source_commit` equal to the observed head, `selection_scope: selected_files_only`,
`files` (path to SHA-256), `git_blobs` (same paths to Git blob IDs),
`source_map_sha256`, `qualification: false` and `promotion_authority: false`.

The publication envelope has exactly these fields: `schema` set to
`merlin-build-publication-observation/2`, `repository`, `branch`, `branch_head`,
`source_commit` (the tested commit), `source_map_sha256`, `status: observed`,
`readback_complete: true`, `tested_manifest_ref`, `published_manifest_ref`,
`qualification: false` and `promotion_authority: false`. Creating this envelope
without authenticated readback is not an admissible substitute for that readback.

## Checks and persistence

The host policy pins both repositories/branches, observed publication head,
workflow path/commit/Git blob/SHA-256, controller Git blob/SHA-256, runner,
native run ID and attempt, artifact ID/name/digest/size. Build-attempt budget and
native run-attempt identity remain separate fields.

The importer verifies the raw archive's provider digest and size, exact equality
of each detached native member, the inner tested-source ZIP, its manifest, and
every selected file's SHA-256 and Git blob identity. ZIP members are inspected
in memory, bounded by count and expanded size; they are never extracted or
executed. The adapter caps archive reads at 8 MiB, metadata/report reads at 1 MiB,
and workflow/controller reads at 64 KiB. The outer and source ZIP expansion caps
are 16 MiB and 5 MiB, with at most 40 and 201 files respectively.

Software acceptance recomputes the inventory from the actual executed IDs and
compares it with discovery, the report and the host goal. The archived
`software-report.json` must agree with the normalized report. Its archived
`software-report.events.txt` must contain a complete, distinct, serial start/stop
pair for every executed test, and its failure/error/skip events must agree with
the exact recorded outcome IDs and counts. Missing, duplicate, overlapping,
unfinished or unrelated test events fail admission. The archived
`live-report.json` must retain the same source anchor/map, role observations and
projected kernel/context case names and Boolean outcomes as the normalized
report. Each raw role must include its actual schema, status, test/pass counts,
scope and authority fields; a case-only fragment cannot borrow missing fields
from the normalized summary. Kernel host UID/systemd identity and context source
identity/model-review scope are required as well. These original measurement
members are mandatory and bounded at 4 MiB
each. The adapter checks their consistency; it does not independently repeat the
kernel experiments or infer hidden measurements from a summary.

Exactly the fixed eight
kernel names and six context names are required. Case counts, individual Boolean
outcomes, source/run bindings, declared inventories and summary flags must agree.
The completed-process recovery case is a separate mandatory context check.
Expected failures, unexpected successes and skipped/failing/error tests cannot
establish acceptance. Before/after service metadata must agree; that observation
is not a comprehensive service audit.

Malformed or inconsistent provenance, references or identities fail admission
before any generated record is written. Complete, internally consistent failed
case observations can produce a bounded repair/stall/budget decision. Incomplete
timeout artifacts do not become successful acceptance evidence; they remain
outside this complete-observation importer.

After all callbacks, the importer re-reads the exact references to detect
mutation. It records `merlin-build-evidence-admission/1` and
`merlin-build-loop-decision/3` as canonical, content-addressed artifacts in the
existing registry. They retain the exact original references and both publication
commits. Original report bytes remain independently available; no second store is
introduced. Persistence is idempotent, but this helper is not a transactional
global attempt ledger or an autonomous scheduler.

`replay_oci_build_decision` receives the **current host-supplied** goal and policy
again, reads the exact recorded decision, reauthenticates every original evidence
reference, recomputes the result and requires the same decision identity before
persisting anything. Stored criteria cannot lower host requirements. Replay is
not a new native execution or an independent review.

## Verification and operational limits

Focused tests use synthetic source, workflow, controller and provider observations
with an explicit fixture-only role/ref/digest allowlist. They cover the original
v2 head mismatch, the checked v3 relation, changed membership/hash/Git identity,
run attempt and controller drift, incorrect inventories and context failures,
truthy authentication, reference/byte mutation, exact archive membership and
deterministic restart replay. An independent synthetic negative control exposed
that the initial importer trusted summaries without checking the retained raw
measurement members. The repair requires those members and tests contradictory
software results, incomplete/mismatched event journals, and raw native case/source
disagreements with consistently re-pinned archive/provider identities. This
prevents contradictions from being mistaken for merely stale artifact hashes.
The unchanged v2 test module remains in the focused
selection. Real native evidence is inspected for schema design only and is not
admitted under that synthetic authenticator.

The maximum successful result is `ready_for_review`. Native model review,
independent-verifier qualification, model efficacy, merge, deployment, permission
changes and automatic retries are never authorized. Live service wiring and the
host's actual authentication/custody integration remain unprovisioned. The
existing native run validates its own frozen source, not this later candidate.

This is an identity/Boolean admission problem. A graph view helps enumerate the
cross-bound report/manifest relationships; alternate simplex, continuum or fuzzy
representations add no acceptance evidence and are deferred. Probabilistic scores
cannot replace exact membership, literal Boolean authentication or permissions.

Rollback is to keep using the unchanged explicit v2 APIs and retain the new
candidate separately. Do not force legacy branch equality or discard the actual
publication-head observation to make a decision pass.

## Final combined local validation

The repaired weight-binding and build-admission changes were independently
reviewed within the same engineering team, then combined without further source
edits. The final 121-file selection executed all 473 software tests (386 existing,
45 weight-binding and 42 evidence-admission tests), with zero failures, errors,
skips, expected failures or unexpected successes. Total local runner elapsed time
was 33.113 seconds on x86_64/Python 3.12.14. All selected source identities matched
before and after execution.

Source-map SHA-256:
`7dfff2dc84b43b9c3c35e0513c31052307ad71ce79f1211f59736bdfa446afe9`.
Executed-inventory SHA-256:
`a70ce5d187c262cddc1a0c31d363d6be54bcb103cb47eae3b7bea87d7207f348`.

The prior 386/8/6 native result belongs to source commit
`4847d90dca4266d42651a8b9538c3eeae8a423b1`. Native acceptance for this new
selection is a separate gate. The source-specific result will be recorded in a
subsequent technical checkpoint. No actual model loading, weight editing or
model-quality improvement was measured, and production host authentication and
live service integration remain unprovisioned.
