# Merlin Learning OIDC bearer-token configuration

**Status:** implemented verifier contract; no production identity provider is configured.

## What this integration is

Merlin Learning can validate signed JWT bearer access tokens issued by an external OIDC identity provider. It is a resource-server integration, not an interactive login/authorization-code client. The upstream OIDC client must perform authorization-code state and nonce validation and obtain the access token. Opaque access tokens require a separate introspection verifier and are not accepted by this JWT/JWKS adapter.

The verifier uses the pinned `PyJWT[crypto]==2.15.1` dependency and PyJWT's `PyJWKClient`. It uses a deployment-configured asymmetric algorithm allowlist, validates the signature, issuer, audience, expiry, issued-at and not-before claims, requires a subject, and enforces a maximum token lifetime. JWKS retrieval is HTTPS-only except loopback development, with a five-second default timeout, a 300-second JWK-set cache, and immediate refresh eligibility for unknown key IDs. The unverified JWT header is used only to select a candidate key; the signature and claims are then verified using the configured fixed algorithm allowlist.

## Environment

Set these values in the trusted server environment, not in browser code or request payloads:

| Variable | Required | Default | Purpose |
|---|---:|---|---|
| `MERLIN_OIDC_ISSUER` | yes | — | Exact issuer identifier from trusted provider metadata |
| `MERLIN_OIDC_AUDIENCE` | yes | — | Audience for the Merlin API |
| `MERLIN_OIDC_JWKS_URL` | yes | — | JWKS endpoint from trusted provider metadata |
| `MERLIN_OIDC_ALLOWED_ALGORITHMS` | no | `RS256` | Fixed comma-separated asymmetric algorithm allowlist |
| `MERLIN_OIDC_TENANT_CLAIM` | no | `tenant_id` | Provider claim mapped to Merlin tenant |
| `MERLIN_OIDC_ROLE_CLAIM` | no | `role` | Provider claim mapped to a Merlin Learning role |
| `MERLIN_OIDC_LEEWAY_SECONDS` | no | `60` | Clock-skew allowance, maximum 300 seconds |
| `MERLIN_OIDC_JWKS_TIMEOUT_SECONDS` | no | `5` | JWKS network timeout, maximum 30 seconds |
| `MERLIN_OIDC_JWKS_CACHE_SECONDS` | no | `300` | JWKS cache lifetime, maximum 3600 seconds |
| `MERLIN_OIDC_MAX_TOKEN_LIFETIME_SECONDS` | no | `3600` | Maximum `exp - iat`, range 60–86400 seconds |
| `MERLIN_OIDC_REVOCATION_DB` | no | unset | SQLite `jti` revocation database for a single-instance deployment |

The provider must issue signed JWT access tokens containing `iss`, `aud`, `sub`, `iat`, `exp`, and the configured tenant/role claims. If a revocation database is configured, tokens must also contain `jti`. Roles are intersected with Merlin's existing role allowlist. A token cannot choose its own accepted algorithm.

Install the pinned verifier dependency with:

```sh
python -m pip install -r requirements-merlin-auth.txt
```

The standalone `serve()` entry point automatically builds the resolver only when issuer, audience and JWKS URL are all configured. Missing or invalid configuration returns no resolver, so LMS routes remain fail-closed. A host may instead inject a resolver explicitly.

## Revocation and deployment scope

`MERLIN_OIDC_REVOCATION_DB` enables an append-only local `jti` denylist. Revoked tokens are rejected on subsequent requests. This SQLite store is for a single-instance deployment; multi-instance deployments must inject a shared revocation checker/service. Without a configured revocation checker, a signed token remains usable until expiry, so keep token lifetimes short and configure the maximum lifetime.

HTTPS is mandatory for non-loopback issuer and JWKS URLs. Never accept issuer/JWKS URLs from a user request. No client secret is needed to fetch a public JWKS; do not add provider secrets to source control. Do not log bearer tokens.

## Not yet completed

- No issuer, audience, JWKS URL, tenant mapping or role mapping has been supplied/configured.
- No real provider-issued access token has been validated against a live JWKS endpoint.
- No interactive login, callback, logout or upstream authorization-code flow is implemented here.
- No shared multi-instance revocation service has been configured.
- Institutional SSO policy, session management, account provisioning, group/role synchronization, FERPA/privacy review and production operational acceptance remain open.

Therefore this code is a tested integration mechanism, not evidence that Merlin Learning currently has production SSO.
