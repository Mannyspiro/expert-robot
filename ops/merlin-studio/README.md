# Merlin Studio on an OCI host

This directory is a **prepared deployment profile**, not a running deployment or
a live web address. It joins the Studio application and its canonical research
state behind one authenticated HTTPS hostname. It does not create an OCI VM,
change a firewall, allocate a paid resource, enroll an account, install a package,
or start a service.

The application remains on `127.0.0.1:8771`. For ordinary browser access, this
profile uses a **named Cloudflare Tunnel with Access**. The address locates the
login gate; knowledge of the address does not grant access. A private Tailscale
route is a useful alternative, with the compatibility boundary below.

## Deployment contract

The service invokes the reviewed app with:

```text
--port 8771
--data-dir /var/lib/merlin-studio
--research-state-dir /var/lib/merlin-research
--gateway-config /etc/merlin-studio/gateway.json
```

`gateway.json` uses the `merlin-studio-trusted-gateway/1` contract. Its one HTTPS
origin must exactly match the public hostname, and its Access team and audience
list must match the connector's per-ingress verifier. Missing or malformed
configuration must stop gateway-mode startup; it must not become an unauthenticated
external-origin mode. The application retains its exact Host/Origin checks and
its per-launch mutation token.

**Identity verification is performed by `cloudflared` before requests reach
Studio.** A `Cf-Access-Jwt-Assertion` header's presence is not cryptographic
verification. The app's explicit gateway mode relies on the configured validating
connector and a trusted local host. Do not place another unvalidated proxy in
front of the app, forward client-supplied identity headers through a bypass, or
strip `Origin`/rewrite a public `Host` to localhost to defeat the local boundary.

The research HTTP surface is read-only, but `/var/lib/merlin-research` is writable
canonical runtime state: trusted Studio publication appends real activity through
the canonical outbox, and SQLite may create WAL/SHM files. This is not an OS
read-only export. Workspace files are not automatically made public research
artifacts; only explicitly registered artifacts are available through that view.

## Host and ownership layout

Use a persistent supervised service, not a long-lived CI job. These paths are
the profile's required installation layout, not claims about the current OCI host.
Inventory the actual host and review the source/runtime identities before staging.

| Path / identity | Intended ownership and access |
| --- | --- |
| `/opt/merlin-studio/current` | Root-owned reviewed release; neither service may modify code. The `current` link is changed only by the release operator. |
| `/opt/merlin-studio/runtime/bin/python3` | Previously reviewed compatible Python, at least 3.10; root-owned and executable by both services. |
| `/usr/local/bin/cloudflared` | Previously reviewed connector binary; root-owned. Its version/hash belongs in the deployment record. |
| `merlin-studio` | Dedicated non-login service account; no sudo, runner, container-daemon, cloud-administrator, or repository-credential groups. |
| `merlin-tunnel` | Separate non-login connector account; cannot read Studio or research state. |
| `merlin-config` | Read-only configuration group for the two services, supplied through `SupplementaryGroups`. |
| `/etc/merlin-studio` | Root-owned directory, mode `0750`, group `merlin-config`. |
| `gateway.json`, `cloudflared.yml` | Root-owned, mode `0640`, group `merlin-config`; contain configuration identities and a credential path, not credential values. |
| `/etc/merlin-studio-tunnel` | Root-owned directory, mode `0750`, group `merlin-tunnel`; inaccessible to the Studio service. |
| `credentials.json` in that directory | Existing named-tunnel credential; root-owned, mode `0640`, group `merlin-tunnel`. Never commit it or put it in browser assets/logs. |
| `/var/lib/merlin-studio`, `/var/lib/merlin-research` | Created/managed by systemd for `merlin-studio`, mode `0700`; survive release changes. |

Do not run the service as the CI runner account or from its writable checkout.
The service's filesystem restrictions, empty capability set, private temporary
directory, and private devices reduce exposure; they are not a claim of complete
host isolation. Approved Python actions run with the Studio account's permissions.
A CI job with privileged access to the same host can defeat a separate account's
boundary. Use a separately isolated VM when the runner accepts untrusted jobs or
has host-level privileges; do not assume a Unix user or container alone solves
that situation. Review the OCI host's actual runner/workload configuration first.

No model, inference binary, or Python distribution is downloaded by these files.
Bind an already reviewed loopback inference service or a compatible supplied local
model. The service's `PrivateDevices` setting is a conservative CPU profile; a
device-backed model requires separate host qualification. A healthy web page
alone does not establish successful model inference.

## Named Tunnel configuration

Use a dedicated **locally managed** named tunnel for this profile. A remotely
managed tunnel uses Cloudflare's remote ingress configuration; copying this file
does not configure it. Do not mix the two modes and claim the local gate verifies
remote configuration.

1. Identify the approved hostname, entitled owner/account, identity provider, MFA
   requirement, and session duration. Create the Access application and restrictive
   Allow policy for the **whole hostname before publishing a route**. Keep every
   API, research graph, artifact and event route covered; review all Bypass and
   Service Auth exceptions. The templates cannot verify the live policy.
2. Fill `gateway.json.example` using the actual HTTPS origin, Access team slug,
   and application audience. The example deliberately contains invalid placeholders.
3. Fill `cloudflared.yml.example` with the same hostname, team and audience, plus
   the existing named-tunnel UUID. Use only the credential file for that tunnel.
   Keep the credential value outside this repository.
4. Preserve `originRequest.access.required: true` **on the matching ingress rule**,
   not only in a top-level default. The last rule returns `404`. No wildcard,
   alternative hostname, path exception or different service target is admitted
   by this narrow profile. `httpHostHeader` remains the real public hostname.
5. Stage the two root-owned configuration files with the ownership above. Run both
   the profile agreement check and the connector's native validation before enabling
   a route or starting the connector.

The `.yml` example uses JSON syntax, which is valid YAML. This intentionally lets
the small agreement checker use Python's standard library. Preserve that syntax;
the checker rejects arbitrary YAML, duplicate keys and unresolved placeholders.
The strict checker admits only this single-app profile, not every possible
Cloudflare configuration. It is not a substitute for `cloudflared` validation.

From the reviewed release, the nonmutating checks are:

```sh
/opt/merlin-studio/runtime/bin/python3 -B ops/merlin-studio/check_config.py \
  --gateway /etc/merlin-studio/gateway.json \
  --tunnel /etc/merlin-studio/cloudflared.yml
/usr/local/bin/cloudflared --config /etc/merlin-studio/cloudflared.yml tunnel ingress validate
systemd-analyze verify ops/merlin-studio/merlin-studio.service ops/merlin-studio/cloudflared-merlin.service
```

The agreement checker validates one HTTPS DNS origin, exact matching team/audiences,
the loopback app and metrics targets, the mandatory per-rule verifier, and the
rejecting catch-all. It rejects symlinked, non-root-owned or group/world-writable
config files. It does not read tunnel credentials, contact Cloudflare, inspect
Access policy, authenticate a user, or change services. Error output deliberately
does not print parsed values or complete files.

After those checks and the live policy review, a qualified host operator can
install the two units, reload systemd, start Studio, and then start the connector.
The units intentionally fail when required accounts, runtime files or configuration
are missing. Do not remove the checks or loosen file ownership to make a failed
start appear successful. Treat unsupported systemd hardening directives as a host
compatibility gap to resolve and record, not as proof that a restriction is active.

OCI NSGs/security lists and the host firewall should leave app port `8771` and
metrics port `20241` inaccessible from the public network, including IPv6 and
alternate interfaces. The named tunnel initiates outbound connections. Do not
open `0.0.0.0:8771` or `:::8771` for the browser route. Preserve the existing
reviewed administration path; this profile does not modify SSH or OCI policies.

## Streaming and browser behavior

Test the actual chat, research-event, graph and artifact routes through the chosen
hostname. The portable chat backend originally returned complete model responses
and the UI polled run state; that is not token-by-token model streaming. The
research event stream and any later streaming transport need their own observed
checks. Use same-origin URLs and preserve normal `Origin` and browser credentials.
Do not create CORS or unauthenticated `OPTIONS` exceptions as a connectivity fix.

Quick `trycloudflare.com` tunnels are unsuitable here: their hostnames are
temporary, they have no uptime guarantee, and they do not support SSE. A named
tunnel with Access is the intended browser route. Proxy support for WebSockets
does not establish Merlin-specific reconnect or session-expiry behavior.

## Private alternative: Tailscale Serve

For only the owner's enrolled devices, private tailnet access avoids a public
application route. Tailscale Serve supplies HTTPS and applies tailnet access
rules; Funnel is public sharing and must remain disabled for this use case.
Use an explicit owner/device policy and a non-sensitive certificate hostname.

**This Cloudflare-specific gateway contract is not a Tailscale authentication
implementation.** Serve does not supply a Cloudflare Access JWT. Do not reuse the
gateway JSON, forge that header, or remove the application's Origin checks to
make it work. A dedicated, verified Tailscale identity adapter (or an independently
authenticated reverse proxy) and corresponding negative checks are prerequisites
for a browser-only Serve profile. Until then, an authorized SSH local forward
that preserves the existing localhost browser origin is an administrator fallback,
not the deployed phone-facing service.

## Acceptance and restart evidence

Before reporting a live URL, preserve the exact app commit, Python and connector
versions/hashes, redacted configuration identities, observed systemd restrictions,
and results of these bounded checks:

- An anonymous browser and an unentitled account cannot access Studio, status,
  mutation tokens, APIs, research events, graphs or artifacts.
- The intended owner can authenticate, use chat, view research and complete a
  harmless authorized workspace operation. Real inference must be observed before
  claiming that the remote model is working.
- Missing, malformed, wrong-audience and expired Access assertions are rejected by
  the validating connector; merely seeing a login page is insufficient evidence.
- Wrong Host/Origin, cross-site mutations and missing mutation tokens remain
  rejected by Studio. No alternate connector route bypasses authentication.
- The raw app and metrics ports are unavailable externally; valid public TLS and
  the actual authorized URL are observed without disabling certificate checks.
- App restart preserves conversations, workspace and canonical research state.
  Connector restart recovers routing. Test active streams and subsequent requests
  separately when a session expires or access is revoked.

Restart changes the local mutation token; the UI must refresh its status normally.
Interrupted jobs are recorded by Studio recovery and must not silently replay
external actions. Back up both complete state directories with the app stopped,
or use a separately qualified SQLite-consistent backup procedure. Retain the
previous reviewed release and gateway configuration. A rollback stops the
connector first and restores known-good code/config without reopening public
origin ports. Do not point an older release at a migrated database without
checking schema compatibility.

## Primary references

Checked 2026-11-25; these describe product capabilities, not this host's live state.

- [Cloudflare Access application and origin token validation](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/self-hosted-public-app/)
- [Named Tunnel outbound connection model](https://developers.cloudflare.com/tunnel/concepts/)
- [Per-ingress Access verifier parameters](https://developers.cloudflare.com/tunnel/reference/origin-parameters/)
- [Cloudflare identity-gated deployment guidance](https://developers.cloudflare.com/reference-architecture/design-guides/identity-gated-edge/)
- [Quick Tunnel limitations](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/)
- [Cloudflare WebSocket behavior](https://developers.cloudflare.com/network/websockets/)
- [Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
- [Tailscale Serve persistence](https://tailscale.com/docs/reference/tailscale-cli/serve)
- [OCI networking controls](https://docs.oracle.com/en-us/iaas/Content/Security/Reference/networking_security.htm)
- [OCI IAM App Gateway, an alternative identity proxy](https://docs.oracle.com/en-us/iaas/Content/Identity/appgateways/understand-app-gateway.htm)
- [Self-hosted runner isolation concerns](https://docs.github.com/en/actions/reference/security/secure-use)
- [systemd service execution and filesystem restrictions](https://www.freedesktop.org/software/systemd/man/latest/systemd.exec.html)
