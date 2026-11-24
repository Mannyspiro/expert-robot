# Wilborn MVP release gate (2026-11-23)

Current state: draft PR; no production launch or real client data. Baseline revision `40b672e2ee2a35efa1f06e5c79e418d42729544e`: 65 tests passed in [unit CI](https://github.com/Mannyspiro/expert-robot/actions/runs/45303195765); [public research probe](https://github.com/Mannyspiro/expert-robot/actions/runs/45303195986) passed and extracted 4,152 characters. These results apply only to that revision. New ingestion/analysis changes require fresh CI.

## Required independent evidence
- Run Python 3.11 workflow tests and preserve exact commit and CI run ID.
- Verify persistence after process restart, tamper detection, denial of sensitive agent actions.
- Check for exposed credentials without printing values; revoke/rotate only using approved provider-side credential broker.
- Threat model: unauthenticated API, client-data access, malicious instructions, secret disclosure, workflow injection and unauthorized agent actions.
- Require human approval before deploying, sending messages, signing documents or accessing customer data.

## Business architecture
ChatGPT: conversational entry point via future authenticated connector.
Titan: encryption scheme (planned qualification and integration; not an AI reviewer).
Merlin: code/research worker, no direct secrets or PII.
Artex: third-party cybersecurity framework; defensive-only passive detection integration, not an independent reviewer or deployed framework.
Protected service: authoritative records, authentication, authorization, audit and approved actions.

## Do not mistake
A source policy for runtime enforcement, unit tests for penetration testing, hash chaining for encryption, or a CI green result for production readiness.


## Security monitoring release delta
The signed local event bridge, encrypted incident history and external anchor verification were exercised on synthetic data at revision 1235a608ee02e0145016b1c5063d8cb18cff356d (101 business tests plus 8 CACE tests, and all three workflows passed). The subsequent summary export e4de2a3652fbcbcdcfa485387c78b6a0eb08ee97 passed 102 business tests plus 8 CACE tests. Studio's separate review candidate is 96cb74a73e0c2d535332a65639b03a6c979e6739, PR #229. These are development evidence, not signed production statements.

The release gate now explicitly requires independently signed statements for authenticated telemetry, encrypted incident history, independent rollback anchor, Studio review integration, isolated OCI qualification and private-host validation. The exact release artifact and source commit must be bound to each statement; an independently held rollback anchor must be current and retained outside the protected ledger.

## Proposed OCI qualification contract — not approved or dispatched
Use only an independently reviewed fixed execution profile, source-pinned to the eventual release candidate. Test synthetic event ingestion, transaction rollback on signer failure, encrypted history recovery in a new process, independent anchor rejection of an older database, and read-only Studio summary display. Require an isolated disposable working directory and nonprivileged execution with no access to real records, private signing keys, production configuration, model workspaces, or other services. Use ephemeral fixture keys and only the already-approved dependency delivery method. Record exact source and test identities, measured results, resource bounds and termination status. No arbitrary command, path, target, secret or credential parameters; no network scanning or upstream ARTEX runtime. Return only a minimized test-evidence manifest, with no key material or raw logs. Existing OCI profiles do not qualify this service; do not dispatch or broaden runner authority until the profile is approved.

## Private-host release gate
Require actual host authentication and authorization, independently administered signer/key custody, an independently retained current anchor, reviewed migration from v1 and archival/retention, private storage and backup/restore verification, reviewed monitoring-source configuration, operator access separation, exact Studio package/source reconciliation, and operator-approved release. The Studio viewer is a synthetic snapshot, not live telemetry. No production host qualification or deployment approval has been obtained. Passing a development test or signing an approval-shaped fixture cannot authorize deployment.

## Durable writer handover requirement — 2026-11-24

The machine-enforced release evidence set now includes
`durable_writer_handover`. The previous 17 statements leave this gate blocked.
The new statement must have its own configured trusted verifier pin and bind
the exact source commit and immutable release artifact through the existing
CACE verifier. A restore-drill statement or a handover statement for another
source cannot substitute. Complete signed evidence still leaves
`production_qualified` and `deployment_authorized` false; this report cannot
deploy or issue a writer lease.

The handover evidence must establish that the predecessor is fenced before
successor writes are accepted, stale writer ownership is rejected, and restart
or interruption at each transition boundary recovers without two writable
segments. It must cover both event ingestion and operator-review mutations,
retain predecessor history and unresolved alerts, and state the storage and
process-lock assumptions. A trusted local host with synthetic ledgers can
exercise those software invariants. It does not establish independent
administration, distributed fencing, power-loss durability on the eventual
host, or production availability. Actual private-host qualification must
repeat the relevant failure and recovery checks under the deployed storage,
authentication, process ownership and backup policies.

The local key and anchor fixtures remain insufficient for operational
custody. Separate keys or owner-only directories under one test process do
not establish separate administrators. Production still requires operator
provisioning of independently administered Titan key/signing custody and a
current rollback anchor retained outside the protected ledger's failure and
restore scope. No private keys, credentials or real records belong in test
receipts or shared-runner artifacts.

Read-only capability verification on 2026-11-24 found that the fixed
[OCI gateway at `3e772229d5effed851c8c666da9127a441e0b2ff`](https://github.com/morganaspim/Cace-app/blob/3e772229d5effed851c8c666da9127a441e0b2ff/.github/workflows/merlin-oci-job-gateway.yml)
has no Wilborn security-monitoring operation. Its inventory, MCP, CACE, RSI
and C++ profiles do not qualify this service. The proposed isolated profile
above remains unapproved and undispatched. The next host gate is review of
one fixed source-pinned synthetic acceptance profile, with explicit resource,
filesystem, dependency and network limits, followed by an actual run on the
authorized isolated host. This is tracked under canonical master-plan v6
tasks `P00-3`, `P00-4`, `P02-3`, `P04-3` and `P04-4`; software tests cannot
close their operational acceptance requirements.

## Repeated handover acceptance delta — 2026-11-24

The `durable_writer_handover` evidence must now cover the implemented bounded
continuation protocol, including permanent retirement, exactly one competing
child destination, intact original enrollment/grants, complete ancestry and
current retained custody on every managed mutation. The eighth segment must
remain usable and exportable; a ninth must fail before retiring the current
owner. A reviewed continuation is required for earlier grants that lack
custody-directory bindings. The existing set remains 18 required statements.
See `SECURITY_GENERATIONS_AND_ACTIVE_REVIEW_20261124.md` for the tested contract
and precise limits.

The existing OCI inventory operation subsequently ran successfully in
[run 45392435551](https://github.com/morganaspim/Cace-app/actions/runs/45392435551)
on the existing runner. This establishes availability during that job. The receipt
explicitly has `qualification=false`; it does not establish a monitoring
profile, runtime compatibility, isolation or independently administered custody.
The proposed Wilborn acceptance operation remains uninstalled and undispatched.
