# Model transport and weight-bound private status

## Completed engineering scope

**The bounded repairs, separate same-team reviews and selected-source local/native
acceptance are complete: 548 software tests, eight kernel cases and six context
cases passed on the exact published source.**

The tested source is commit
`4b1d5e75916570e0a2d37cc2371b3dc27339ad9a` in
[PR187](https://github.com/Mannyspiro/expert-robot/pull/187), continuing PR186
from parent commit `196e3c5fa953c638f81db627c3e86f32eaf50a59`. All 125 selected
Git blobs and all eight changed source/test file readbacks matched the local
tested bytes. A separate documentation commit does not change that tested
source identity. This is a selected-source result, not whole-repository or
full-platform acceptance.

The existing canonical registry, workflow, private dispatcher and application
routes remain the integration points. No alternative receipt store was added.
The private CLI remains read-only and cannot configure a provider callback.
No actual checkpoint loading, loaded-weight observer, genuine custody
authenticator or model-quality improvement is established by these repairs.

Exact source-file hashes, parent linkage, evidence locators, retained limits and
next gates are recorded in the narrow
[local checkpoint](../../config/merlin/plan-updates/20261121-transport-bound-status-local-checkpoint.json).
The parent is
`config/merlin/plan-updates/20261121-weight-binding-admission-native-result.json`,
verified at Git blob `56eac5423128a2fa468c0bfe8d53ce5163f850db`. The appended [native result](../../config/merlin/plan-updates/20261121-transport-bound-status-native-result.json)
records the actual completed run. The consolidated master plan remains unchanged.

## Measured local acceptance

| Identity or result | Observed value |
|---|---|
| Selected source | 125 files, unchanged during the run |
| Source map SHA-256 | `845930b35020bb1aa4b3c67f8c21dccf16e9a09466de7dc00fa3b843b4aa042c` |
| Executed software tests | 548 passed |
| Failures / errors / skips | 0 / 0 / 0 |
| Expected failures / unexpected successes | 0 / 0 |
| Recorded starts / stops | 548 / 548, with the exact declared IDs |
| Executed inventory SHA-256 | `e80d6d61dbf67b6872e492be37af78925ee0bf1b8f3c2ac52c1a773bccc2bfc8` |
| Runtime | x86_64, Python 3.12.14 |
| Elapsed time | 53.377 seconds |

The combined record is retained under
`verification/loopback-continuation/`, including the measured software report,
event journal, raw test log, source manifest and publication readbacks. The
checkpoint records their hashes. The focused suites below are component
subsets, not extra tests to add to the combined total.

| Boundary | Focused evidence | Separate review/control result |
|---|---|---|
| Council transport | 16 tests passed | The same five independent controls changed from two passes and three original failures to five passes |
| App chat/speech transport | 12 tests, 39 subcases passed | Original handler redirects and synthetic credential forwarding reproduced; repaired routing and generic credential errors accepted |
| Bound status and workflow references | 92 tests passed: 36 private-status and 56 weight-binding tests | All 16 mutation controls rejected after repair; representative independent record and current-policy checks accepted |

Separate same-team reviews accepted these exact repaired boundaries. They do
not constitute an external verifier attestation or model qualification.

## Original defects and retained controls

The original council client checked only the initial HTTP loopback URL and
then used the default urllib opener. Five controls on the preserved original
source reproduced three failures: a 302 redirect selected a nonloopback
destination, an environment proxy received the synthetic POST, and a changed
`localhost` resolution selected a nonloopback destination. Actual sockets were
fenced to temporary loopback fixture ports. The redirected GET contained no
POST body; the proxy and resolver controls did receive the synthetic request
body. No external endpoint, actual credential or model was involved.

The adjacent local chat and speech handlers followed redirects to a second
local fixture. A cloud control exercised urllib's actual redirect processor
with a memory-only HTTPS connection fixture: the synthetic Authorization header
was forwarded from an allowlisted fixture hostname to an unallowlisted one.
This is client-routing evidence, not an actual TLS or provider execution.
Earlier incomplete fake-connection attempts remain explicitly labelled in the
record. Independent review also reproduced an invalid-header exception that
echoed a malformed synthetic API key; the corrected path now returns a generic
error before creating a connection.

The original private status handler constructed an unbound workflow for every
session. A completed bound session could be inspected directly with its host
binding, while the authorized dispatcher rejected it. This was reproduced
without additional provider calls or registry writes. Local AF_UNIX creation
was denied with EPERM, so the private-status controls exercised the actual
dispatcher and canonical read-only registry, without claiming Unix transport
coverage.

Review then exposed a shared evidence race: an authenticator could change an
already-read receipt and return `True`, allowing completion to be reported even
though a fresh read rejected the same canonical reference. Bounded sibling
controls found equivalent gaps for other workflow records. The before/after
controls, rejected observations, original source versions and callback counts
were retained. Additional current-policy controls showed why the new status
callback path also needed context and grant checks before returning its result.

## Implemented transport contract

The council client connects directly to a numeric loopback address.
`localhost` means IPv4 loopback `127.0.0.1`; an IPv6 service uses an explicit
`[::1]` URL. Original URL text is validated before parsing. User information,
fragments, control characters, malformed ports and malformed escapes are
rejected before I/O.

Local chat and speech reuse this parser and use direct `HTTPConnection` calls.
Cloud chat retains its qualification switch, configured API key, exact hostname
allowlist and HTTPS requirement. It uses direct `HTTPSConnection` with the
standard verified TLS configuration. The host API key is checked for control
characters and supported HTTP-header encoding; invalid values produce a generic
message without exposing the key. The cloud fixtures verify constructor and
routing behavior; they do not demonstrate a real certificate exchange.

These model paths do not follow redirects or use environment proxies or the
global urllib opener. Non-success upstream responses are rejected before the
body is exposed. The response and connection close on success, failure and
early return. Existing qualification flags, request payloads, browser-origin
checks, telemetry, response readers and their bounds remain in place:

- Council response: 256,000 bytes.
- App request body: 1,000,000 bytes.
- Nonstream app response: 16,000,000 bytes.
- Streaming app response: 64,000,000 bytes, with the existing 8,192-byte reads.
- Council/chat socket timeout: 180 seconds; speech socket timeout: 60 seconds.

These are per-operation socket timeouts, not total execution deadlines. The
existing streaming error behavior was preserved; this repair does not redesign
HTTP error framing after a stream has begun.

## Implemented bound-status and evidence contract

A trusted embedding host may supply
`rsi_weight_binding_resolver(session_id)` to `PrivateDispatcher`. The resolver
returns an existing `WeightBinding` for the exact registry object and project.
The client request accepts only the session identifier; it cannot select a
manifest, provider, callback or host configuration.

Peer, tool, session and context checks precede the resolver. A bound session
without a provisioned binding returns the bounded
`weight_binding_not_configured` error. Unbound v1 sessions retain their behavior
and do not consult the resolver. Status reauthenticates canonical evidence
without invoking coder or evaluator callbacks and without enabling registry
writes.

The shared workflow now re-resolves consumed canonical records after the
existing authentication callbacks and before dependent callbacks, reports or
status results rely on them. Exact reference identity, canonical bytes and the
existing single-version workflow rule remain enforced. Corruption and new
versions invalidate the current operation. The readbacks do not recursively
authenticate or retry providers, and ambiguous prior effects remain blocked
for reconciliation.

The private status path rechecks the same context references after resolver and
authentication callbacks. Before returning `rsi_status`, it also compares the
current UID grant—including principal and tool tuple—with the detached
pre-handler snapshot. Observed in-flight revocations now reject the current
reply. This stronger egress check is limited to status; plugin and pending-job
semantics are unchanged. These checks are bounded observations, not an atomic
transaction against arbitrary concurrent writers.

## Defect-family prevention

| Invariant | Preventive control |
|---|---|
| Model transport preserves the configured destination policy | Direct destination-specific connections; strict original-text validation; redirect, proxy, resolver and global-opener controls |
| Host credentials never become API error details | Generic credential validation before transport; real header-serialization negative control with a synthetic marker |
| A bound status read retains its separately provisioned host binding | Resolver absent/invalid/wrong-registry/wrong-project controls; no unbound fallback; unchanged v1 controls |
| Evidence remains valid after host callbacks | Exact-reference readbacks and corruption/version-append fault injection at existing callback boundaries |
| Status respects current context and caller grants | Context and exact grant checks at egress; resolver/authenticator revocation controls |
| Recovery does not repeat an ambiguous effect | Provider-call counters, unchanged authentication counts, retained intermediate records and no automatic retry |

The controls retain failed and null observations. Passing hashes, schema checks,
host fixture callbacks and model declarations do not independently establish
runtime custody, model quality or promotion authority.

## Measured native acceptance and remaining host/model gates

[Native run 44904879833](https://github.com/morganaspim/Cace-app/actions/runs/44904879833),
attempt 1, completed successfully on aarch64 / Python 3.9.25. The exact 548-test
inventory passed in 157.052 seconds with 548 distinct start/stop pairs and zero
failures, errors, skips, expected failures or unexpected successes. All eight
kernel cases and six context cases passed. Root and a separate reviewer checked
the actual downloaded evidence, including 11 process receipts and the recorded
one-launch checker-only recovery.

The downloaded artifact is 607,499 bytes with SHA-256
`e6aa9cd4766e154dff4f4a8912ca4d07719ebf5e3bd7c418744948d6cce77b2a`.
All 125 archived source hashes and Git identities match the published candidate.
The four recorded service properties were unchanged. This result covers the
declared synthetic engineering cases, not a loaded model, external attestation,
production admission or rollout.

The fixed overlay retains all original byte/time limits. Its full-file attempt
was too large; an exact, baseline-hash-checked splice representation for one
fixed file brought it within the existing ceiling. The rejected attempt and
33 package controls remain in the checkpoint. No source code or controller is
mirrored into the retained evidence archive; their exact Git identities remain
the recovery references.

The remaining production gates include genuine host authentication/custody and
live registry/service integration; Unix peer/context/grant behavior on the
intended host; a permitted editable checkpoint or declared network architecture
with actual loaded-byte observations; representative baselines, independent
task oracles, held-out evaluation and candidate/forward-pass/cost limits; and
the remaining restore, telemetry, domain-integration and release-approval work.
No real model has been loaded or edited by this repair, and no model-quality
gain has been measured.

Rollback is a reviewed reversion of the eight-source change with the optional
host resolver omitted. No rollback, merge, deployment, model installation,
permission change or promotion is performed by this checkpoint.
