# Fjord Commons → ChatGPT: secure MCP onboarding

**Status:** preparation only; Forgejo/Fjord not connected to ChatGPT.

## API and connector distinction

Fjord Commons is a no-card shared Forgejo instance with standard `/api/v1` API.
The API is REST, not an MCP endpoint. ChatGPT cannot use it as a custom MCP
server without a separately hosted MCP adapter. Do not invent a Forgejo URL;
copy the actual HTTPS Forgejo origin from your signed-in Fjord Commons dashboard.

## Read-only authorization first

1. Join the **Commons** plan at https://fjord.sh/commons. Do NOT provision a
   billable dedicated Fjord instance.
2. Open Forgejo from Fjord and go to **Settings → Applications → Access Tokens**.
   Create an account token named `expert-robot-readonly` with the smallest
   allowed repository/read scopes. No `write` or `all` grant unless the UI
   makes it unavoidable, in which case STOP and review.
3. The token stays in an OS secret store on the already available Plesk server.
   Never paste it in chat, commits, command-line flags or workflow logs.
4. Independently verify `GET /api/v1/user` and a read-only repository GET
   against the confirmed HTTPS origin. Never follow cross-origin redirects
   with the token. Reject unexpected response schemas.
5. Self-host the maintained open-source `forgejo-mcp` server on the existing
   server with a fixed release and reviewed license:
   https://github.com/goern/forgejo-mcp
6. Prefer a private Secure MCP Tunnel if your ChatGPT/Platform account is
   eligible. Do not expose the MCP endpoint unauthenticated on a public port.
   See https://developers.openai.com/api/docs/guides/secure-mcp-tunnels and
   https://developers.openai.com/plugins/deploy/connect-chatgpt .
7. Create a private plugin only after an actual Streamable HTTP MCP endpoint
   or tunnel is verified. The external Forgejo API URL is NOT that endpoint.
   Start with list/read/get tools; enable writes only after separate owner
   approval and independent testing.

## Strict no-new-spend constraint

Commons is free forever within its limits: 25 repositories, 5 GB storage,
private repos allowed, public-only shared CI. Existing Plesk hosting must
already be available. OpenAI Platform API key/tunnel access and any billing
implications are **not** established, so require explicit review before
starting either. No paid Fjord dedicated instance, cloud VM, domain purchase,
trial upgrade or billable API calls should be provisioned by this workflow.

## What is and is not done

A deterministic local probe with blocked redirects and read-only endpoints
was created as a connection starter pack and its offline tests passed.
No Forgejo token, SSH login, tunnel ID, live Forgejo instance, or plugin
installation has been seen or tested. Keep source-of-truth GitHub intact
until migrations and credentials are independently verified.

Sources:
- https://docs.fjord.sh/platform/commons
- https://github.com/goern/forgejo-mcp
- https://developers.openai.com/api/docs/guides/secure-mcp-tunnels
