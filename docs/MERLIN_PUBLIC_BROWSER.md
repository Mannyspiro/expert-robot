# Merlin public research browser

## Capability and caller

This addition gives Merlin an anonymous, rendered Chromium research worker. It
accepts a bounded plan of public web actions, retains the actual responses and
rendered observations, and returns canonical `ArtifactRef` evidence through a
typed Unix API. Public destinations are general: there is no source-domain
allowlist. ChatGPT domains are excluded by the user's direction. The browser
does not use a ChatGPT account, the user's existing browser, or imported cookies.

Before this addition, `DotContextBridge` preserved manually supplied source
bytes and supported retrieval/handoffs; it did not acquire or render webpages.
The new worker supplies that missing acquisition step. It reuses
`MerlinRegistry`, `ArtifactRef`, and `DotContextBridge` without modifying their
existing code or the deployed private runtime's grants.

The installed caller is `merlin.browser_client`. The supervisor socket is
`/run/merlin-public-browser/browser.sock`, mode `0660`, owned by root and the
verified `opc` group. The supervisor checks Linux `SO_PEERCRED` and accepts only
UID 0 or Merlin's UID 982. Group membership alone does not grant the API.
The supervisor runs one episode at a time through the fixed root-owned launcher
`/opt/merlin-public-browser/current/bin/launch-episode --episode ID`.
Callers cannot choose a launcher, shell command, executable, file path, registry,
or browser profile through the API.

The new research registry is explicitly
`/var/lib/merlin-public-browser/registry`, project `merlin-browser-research`.
This uses the canonical registry implementation. The existing
`/var/lib/merlin-dot-private/state` and its read-only project remain separate and
unchanged. The browser API itself exposes the new observations and handoffs;
their appearance in the old private service is not implied.

Example action plan, supplied as a JSON file:

```json
[
  {"action":"open","url":"https://github.com/python/cpython"},
  {"action":"read","start_byte":0,"length_bytes":16384},
  {"action":"scroll","delta_y":720}
]
```

After installation, a caller with the authorized UID can use the runtime's
Python environment and source path:

```bash
PYTHONPATH=/opt/merlin-public-browser/current/python \
  /opt/merlin-public-browser/current/venv/bin/python -m merlin.browser_client \
  submit --episode research-001 --actions /path/to/actions.json

PYTHONPATH=/opt/merlin-public-browser/current/python \
  /opt/merlin-public-browser/current/venv/bin/python -m merlin.browser_client \
  read --episode research-001 --observation o0001 --kind text

PYTHONPATH=/opt/merlin-public-browser/current/python \
  /opt/merlin-public-browser/current/venv/bin/python -m merlin.browser_client \
  status --episode research-001
```

These are the implementation's callable interfaces. Actual host installation,
UID 982 access, native compatibility, and post-restart readback require the
separate deployment acceptance receipts; local unit tests alone do not establish
that the service is live.

## Supported actions

| Action | Input | Result and limits |
| --- | --- | --- |
| `open` | Public HTTP(S) URL | Navigate and capture a rendered page. Only standard ports 80/443 are accepted. |
| `search` | `query`, optional GET URL `template` containing one `{query}` | Navigate to a real search results page. Default is Bing; a caller may choose any public search template. |
| `follow` | Latest `observation_id` and one of its `link_id` values | Navigate to the exact observed anchor URL. Stale and invented IDs fail. |
| `back` | No extra fields | Return through the episode's browser history and recapture. |
| `scroll` | Integer `delta_y` from -1440 to 1440 | Scroll the rendered page and capture the resulting viewport. |
| `read` | Optional `start_byte` and `length_bytes` | Recapture and return an exact bounded UTF-8 text range. Default length is 16 KiB. |

The worker also has a JSONL action interface on standard input, with one JSON
result per action. The installed supervisor accepts a bounded plan. A research
caller can inspect returned link IDs and captured URLs, then submit a subsequent
episode using selected URLs. The supervisor does not keep an unbounded browser
session alive between requests. The API `read` operation supports pagination of
text, DOM, original main-document response bytes, viewport PNG, and observed
links from completed episodes; it does not relaunch the browser.

Arbitrary JavaScript, arbitrary selectors, form submissions, uploads,
downloads, account login and storage-state import are not exposed. The browser
executes ordinary webpage JavaScript inside its isolated renderer. Cross-page
popups are closed. Service workers and WebSockets are blocked. A page that
changes its address through the History API without a matching committed
document response must be explicitly reopened before source capture; the
worker does not guess which response belongs to that URL.

## Isolation and budgets

The browser renderer and public egress broker run as the same dedicated nonroot
`merlin-browser` UID in separate process and mount environments. The renderer
has a private network namespace containing only loopback. It can reach only the
broker's private Unix socket through the episode's mounted socket directory.
The broker has normal network access, but every request is mediated by the
public-address policy. The browser receives neither the research registry nor
the private Merlin runtime, host homes, model files, GitHub credentials or
account sessions.

The renderer checks its actual Linux state before launching: nonroot UID,
zero effective capabilities, `NoNewPrivs=1`, and only a loopback network
interface. These checks complement the pinned launcher's mount, cgroup and
absolute process deadline evidence. A caller-supplied isolation label cannot
enable the worker.

Every HTTP request is restricted to GET or HEAD. The broker validates every DNS
answer, rejects private, local, metadata, multicast, reserved and translated
address ranges, and connects directly to the checked numeric address. HTTPS
retains the original hostname for certificate verification and SNI. A second
DNS resolution cannot redirect that connection to a private endpoint. Redirect
destinations are checked before returning a redirect to the browser. Request
authorization/cookie headers and response `Set-Cookie` are not passed through.
Environment proxies and client certificates are not inherited.

| Active default bound | Value |
| --- | --- |
| Episode wall clock | 60 seconds, plus fixed supervisor cleanup deadline |
| Action / request time | 15 / 10 seconds |
| Actions / browser requests | 8 / 64 |
| Main browser context / page | 1 / 1 |
| Response body per resource / episode | 1 MiB / 8 MiB |
| Captured text / DOM per observation | 256 KiB / 512 KiB |
| Viewport PNG | 1 MiB, 1280 × 720 viewport |
| Total episode evidence | 12 MiB |
| Observed links per capture | 100 |
| Model calls / external model cost | 0 / $0 |

Failed and incomplete reads spend the body bytes already consumed. A maximum
one-byte detection overrun is retained explicitly when a body exceeds its
remaining budget. Header lengths are bounded separately. DNS has a bounded
resolver wait; the external process limit is the final bound for hostile or
stalled browser/HTTP behavior. A request storm latches the episode's failure
state and does not exhaust the final failure-record budget.

Before admitting an episode, the supervisor checks free space on both permanent
evidence filesystems for the configured capture copies, bounded exported logs
and an additional 1 GiB reserve. It denies a new launch when space is low and
never deletes old evidence to make the request fit.

## Evidence and canonical ingestion

Each successful observation retains the exact original main-document response
bytes, rendered UTF-8 text, rendered DOM and viewport PNG. The observation records
the full acquired URL, HTTP status, title, capture time, link IDs, truncation
flags, source resource identity and artifact digests. All actions, failures and
resource outcomes are stored in an ordered hash-linked event sequence. Response
headers needed to interpret the retained main document are included after
credential-bearing headers have been removed.

The final manifest contains compact references to observation events, so large
link metadata does not duplicate itself into the finalization budget. File
creation is exclusive; a prior episode is not overwritten. Reusing an episode
ID never repeats a possibly completed launch. If a supervisor stops after a
request has been retained but before a final receipt exists, status returns
`reconciliation_needed` and does not retry automatically.

After the renderer stops, `browser_ingest.validate_episode` verifies the exact
file inventory, digests, byte bounds, event chain, action-to-observation lineage,
main-document response binding and declared kernel/engine metadata. Independent
native host receipts remain necessary to attest the execution environment;
internally consistent JSON cannot independently prove a browser was run.

All validated files are persisted as canonical `ArtifactRef` versions under
`browser/episodes/ID/`. `publication.json` returns those references and a browser
handoff. The handoff includes every captured source, including query/HTTP sources
and eligible sources from an episode with a later failed action.

The existing context bridge requires HTTPS, no query/fragment, a bounded URL and
nonempty source text. This contract remains unchanged:

| Capture | Context intake |
| --- | --- |
| Successful action, 2xx HTTPS document, exact query-free URL, nonempty text | Exact rendered text enters namespace `rsi` as `source_snapshot`. |
| HTTP, query-bearing URL, or URL beyond the bridge metadata bound | `ineligible_url_contract`; all browser evidence remains canonical. |
| Failed action, unsuccessful HTTP status, or empty text | Explicit status describing why context intake was skipped. |
| Existing bridge context-record ceiling reached | `context_capacity_exhausted`; browser publication and readback still succeed. |

No URL is silently stripped of its query or changed from HTTP to HTTPS.
Blank titles receive an explicit source-host label. A bridge session handoff is
created only when there are eligible source references. The browser handoff is
always created for a valid episode, including an entirely failed episode.

Evidence hashes establish byte identity and lineage. They do not establish the
truth of a webpage, source authorship, formal mathematical correctness, improved
model capability or authority to promote a candidate. Captured content remains
untrusted data and cannot issue commands to the worker or publisher. Navigation
traces can later be evaluated as training or policy evidence through existing
research gates; this addition does not train, select or deploy a learned policy.

## Runtime compatibility and verification

The host is Oracle Linux 9.8 aarch64 with Python 3.9.25. The installer uses an
individually pinned Playwright 1.60.0 ARM64 wheel set and a signed native Chromium
package. This version choice preserves the existing Python boundary. The code
uses routing and WebSocket interception APIs available before Playwright 1.60.

Playwright's official documentation states that a custom executable needs care,
that Chromium sandboxing defaults to false, and that routing must block service
workers to see those requests. The implementation explicitly enables Chromium
sandboxing, blocks service workers, installs WebSocket routing before research
navigation, and sanitizes both the Node driver and Chromium environments. Native
Oracle Linux/custom Chromium compatibility requires the actual rendering test;
it is not inferred from package installation.

Primary API references:

- https://playwright.dev/python/docs/api/class-browsertype
- https://playwright.dev/python/docs/api/class-browsercontext
- https://playwright.dev/python/docs/network
- https://playwright.dev/python/docs/docker
- https://pypi.org/pypi/playwright/1.60.0/json

Run the targeted local contract suite with:

```bash
PYTHONPATH=python python3 -m unittest discover -s tests -v
```

The suite uses real HTTP parsers, actual canonical registry persistence and
synthetic page/launcher doubles. It covers private-network policy, DNS pinning,
truncated and partial bodies, byte budgets, metadata exhaustion, failed
navigation, stale links, provenance tampering, source intake, restart readback,
caller authorization, launch failure recovery and UTF-8 pagination. Synthetic
page tests are explicitly not native rendering evidence.

The local workspace's actual sandbox-enabled Chromium launch failed at
`socket()` with `Operation not permitted`; no `--no-sandbox` fallback was used.
Production acceptance therefore requires the separate OCI fixture to execute
JavaScript and capture a real PNG, followed by public-source episodes, UID 982
API calls, readback after service restart, and preservation of the existing
private runtime/provider/state. Failed acquisition attempts remain evidence.
