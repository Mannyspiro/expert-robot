# Fjord Commons ↔ ChatGPT connector — Phase 1 checkpoint (2026-10-09)

## Scope and artifacts

A private ChatGPT onboarding plugin, `fjord-forgejo-setup` (backend ID `plugins_6ac97fa795848191929056e071721c24`), is now created in the user's account, but **no live Fjord connection has been established**. [Open private plugin](https://chatgpt.com/plugins/plugins_6ac97fa795848191929056e071721c24).

A separate read-only MCP bridge source archive was generated in the conversation (not yet deployed on the Plesk server). Its contents are `forgejo_client.py`, `server.py`, `requirements.txt`, example environment/systemd/MCP configuration, README and six offline Python tests. All six network-free unit tests passed.

### Server design

- Forgejo official `/api/v1` endpoint; exact URL must be taken from the actual Fjord Commons forge after login, not guessed from the dashboard.
- Read-only scope: current account, accessible repositories, repository metadata, open PRs, open issues, commit metadata, and small UTF-8 files.
- The adapter rejects arbitrary URLs, external redirects, relative-path escapes, large/binary responses and disallowed methods.
- The MCP server uses the Python MCP SDK v2 and a mandatory in-process ASGI bearer gate; only loopback port 8895, behind manually configured trusted HTTPS on the existing Plesk server.
- **Separate tokens:** Forgejo read-only token stored server-side and ChatGPT MCP client bearer token entered into the official connection UI. Neither token belongs in source code, plugin manifest or conversation.
- Because there is not yet a verified HTTPS MCP endpoint, the private plugin deliberately has an empty `mcpServers` map and only an onboarding skill. After authenticated endpoint verification, UPDATE this plugin (do not duplicate it) to include the exact server URL plus `extensions.com.openai.auth = {"type":"api_key","headerScheme":"bearer"}`.
- **No deployments, writes, merges, production authority, OCI usage, paid trials, or bills were authorized.**

## Next checkpoints

1. User signs into [Fjord Commons](https://fjord.sh/commons), joins free shared Forgejo, shares **only a non-secret Forgejo repository/forge URL**; no tokens or passwords in chat.
2. Obtain verified Plesk admin SSH access and an operator-verified HTTPS hostname. Deploy bridge in a constrained non-root service under TLS after checking dependencies and the host's existing budget.
3. Verify 401 without credentials and successful private account `fjord_whoami` using the secret in the official client connection UI; test repo metadata reads.
4. Update existing private plugin with verified URL, complete user-managed connection and independently verify its listed tools.
5. Preserve GitHub backup until repository migration is audited, and keep scientific proof/RSI gates unchanged.

**No live authentication has been tested.** The overall project progress score remains 22/100 estimated and autonomous research operations remain unqualified pending actual repeated scheduled runs.