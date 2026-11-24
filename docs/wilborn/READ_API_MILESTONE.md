# Read-only API milestone

Scope: loopback-only demonstration service with synthetic, non-sensitive case records.

- `WILBORN_DEMO_TOKEN` is mandatory (at least 32 characters).
- `WILBORN_DEMO_DB` selects a local SQLite demo database.
- Run `python -m wilborn_ops.read_api` to listen on 127.0.0.1:8768.
- GET /health and GET /v1/cases require an Authorization: Bearer token.
- POST is disabled. No write operations, PII, TLS, OAuth, remote binding, ChatGPT integration or live Merlin/Titan/Artex runtime.
- This is **not** suitable for public network exposure. Do not proxy it to the internet or use it with client data.

Next: replace static token with identity-aware authentication and real server-side RBAC, implement audit/retention and independent security review, then a secured ChatGPT connector. Keep API on loopback until those gates pass.
