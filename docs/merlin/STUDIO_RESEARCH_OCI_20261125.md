# Combined Studio and canonical research

## Delivered

Merlin Studio now serves chat, workspace files, tool approvals, its existing
synthetic security review, and the canonical research window from one application.
The new Research panel retains the HUD emblem and motion controls, recorded-run
selection, exact registered graphs, proof/source reading, and graph-follow behavior.
Current Studio requests publish actual metadata into the canonical outbox with
stable event identities. Task completion does not imply scientific verification.

Run updates use bounded Server-Sent Events with reconnect support. Model responses
still arrive when complete; token-by-token model streaming is not implemented.
Conversation text, tool arguments/results, and workspace files are not automatically
registered as research artifacts. The selector covers up to 200 recorded sessions;
the HUD projects the latest 1,000 canonical telemetry records.

Start a local instance with an explicitly separate canonical state directory:

```sh
python3 -B portable/merlin_studio/server.py \
  --port 8771 \
  --data-dir /path/to/studio-state \
  --research-state-dir /path/to/research-state
```

The listener remains loopback-only. The state directory uses the existing registry,
knowledge graph, and outbox formats. Python execution and workspace files belong to
the Merlin host; they do not run on a remote browser user's phone or computer.

## Local evidence

The application/profile sources in this change have 114 distinct passing local
tests: 36 Studio, 19 synthetic security review, 12 integration/HTTP/gateway/SSE,
15 research-window, 25 bounded-registry, and 7 deployment-configuration tests.
The reviewer independently repeated the 12 integration and 19 security tests.
Twelve actual concurrent streams were accepted, the thirteenth received HTTP 503,
and the stream slots recovered after client disconnects.

The source-only ZIP contains 46 shipped files plus the manifest. Every shipped
file matched the explicit source projection; integrity verification and all twelve
integration tests passed from the extracted package. The ZIP includes no model,
Python distribution, inference engine, credentials, or user state.

Package SHA-256:
`bcd475fdc6e33b5c6bad7201b7c6a19e0fb37c823b836728e22053193703a171`

The canonical registry and its bounded-read regression suite remain unchanged from
accepted Studio base `77598ab399d17f5d5d60e0ea907a7394d6851b46`. Canonical HUD changes
carry forward the reviewed research-window implementation with bounded artifact
reads. The public [validation receipt](../evidence/merlin-studio-research-public-20261125/validation.json)
binds exact changed source bytes. Repeated test executions are not added to the
distinct-test total.

Rendered browser acceptance remains incomplete: the browser could not connect to
the local preview, and inspection of its internal error page was blocked. Local
HTTP document and API acceptance does not establish a rendered browser session.
No live cloud identity policy, remote model, or public endpoint is qualified by
these tests. Infrastructure inventory and detailed host receipts are excluded
from this public change.

## Prepared hosting profile

The [operator guide](../../ops/merlin-studio/README.md) and service templates prepare
an owner-only named Cloudflare Tunnel with Access, forwarding to the loopback app.
Configure the Access application before publishing its hostname. The connector's
mandatory per-ingress verifier validates the configured team and audience; the
app itself does not cryptographically verify JWTs. It preserves exact Host/Origin,
Fetch Metadata, and per-launch mutation-token checks. This is one owner's shared
workspace, not a multi-tenant service.

The app and connector have separate service identities, root-owned code/config,
persistent state directories, and supervised systemd units. A privileged CI
workload can defeat same-host service-user isolation; review the actual deployment
boundary. Run the webapp independently of the CI job lifecycle.

The examples contain deliberate placeholders and do not provision resources or
start services. Persistent host administration, a controlled hostname, the intended
owner/Access application, a compatible Python runtime, and a reviewed model service
are still required. The combined app is **not deployed to OCI**, and no public
Merlin address is verified.

After configuration and installation, the next bounded acceptance is actual owner
login and anonymous denial, real inference, tool approval, research artifacts,
activity reconnect, session expiry, and restart persistence through the chosen
HTTPS hostname. Preserve credentials outside chat, source files, and browser assets.
