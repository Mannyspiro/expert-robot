# Free Fjord Commons → ChatGPT MCP Connector (deployment-ready source, not deployed)

**Hosting:** Cloudflare Workers Free + Workers KV Free (no card required).
**Source:** adapted from Cloudflare's MIT-licensed "remote-mcp-github-oauth" demo.
**Forgejo host:** https://commons.fjord.host only.
**Account login allowlist:** morganaspiro; **repository owner allowlist:** the signed-in account and previously supplied Commons namespace.
**Tools:** five read-only operations, no push, merge, delete or write tools.
**Credentials:** NO token is embedded in these files. OAuth browser login supplies Forgejo access.
**Important:** Forgejo OAuth grant scopes have not been verified against this exact
Fjord 15.0.8 instance. Restricting MCP tools to GET calls does not guarantee an
upstream OAuth token has only read privileges. Review Forgejo consent scope before
using with sensitive production repos.

## Setup (once, when the user is ready)

1. Sign up for [Cloudflare Workers Free](https://dash.cloudflare.com/sign-up/workers).
   Do not add a payment method, enable a paid subscription, or choose paid AI.
2. Deploy code under integrations/fjord-cloudflare-mcp using Cloudflare's Git
   integration or Wrangler. Use the Cloudflare Worker subdomain (no domain purchase).
3. Create free KV namespace OAUTH_KV and place its ID in wrangler.jsonc.
4. In signed-in Fjord Forgejo, go to user Settings > Applications >
   Manage OAuth2 Applications. Register a new application named
   "Fjord Commons ChatGPT Read-Only" with callback
   `https://fjord-commons-mcp.<your-cloudflare-subdomain>.workers.dev/callback`.
   Verify OAuth application feature availability and exact read scopes first.
5. Configure Cloudflare Worker SECRETS, not repository files or chat:
   FORGEJO_CLIENT_ID, FORGEJO_CLIENT_SECRET, COOKIE_ENCRYPTION_KEY
   (random 32+ bytes).
6. Validate read-only OAuth flow with MCP Inspector using
   `https://fjord-commons-mcp.<your-subdomain>.workers.dev/mcp`.
   Verify only `morganaspiro` can authenticate; test rejected identities,
   attempted owner escaping, and expired state.
7. ChatGPT plugin connection requires an eligible supported MCP app surface.
   The user's Plus account may not support registering an arbitrary remote
   MCP app through developer mode; check Settings > Apps availability first.
   If supported, create the private MCP app and approve the OAuth login.
8. Only then call list_repositories and get_repository. Maintain GitHub as
   source of truth until a private Fjord repo has been migrated and checked.

## Security and quotas

- The previously pasted access token is **NOT USED** in this integration.
- Source and upstream token credentials never appear in the repo or chat.
- Fixed HTTPS origin; manual redirects; capped JSON payloads; read-only tools;
  account and repository-owner allowlists; one-time OAuth state/CSRF protection.
- 100,000 Workers requests/day free; 100,000 KV reads/day,
  1,000 KV writes/day and 1GB storage free (limits change; verify current plan).
- Cloudflare free usage caps cause operations to fail rather than silently
  upgrading to paid cloud resources. No external training/paid APIs used.
- This is an **initial adaptation** and has NOT passed a complete deployed
  OAuth integration audit. Do not put it into production until you validate
  consent scopes, callback redirects, actual dependencies, and identity limits.

## Reproducibility

`npm install`
`npm test`
`npm run check`
`npm run deploy` (requires Cloudflare sign-in; perform only after verification)

Cloudflare upstream: https://github.com/cloudflare/ai/tree/main/demos/remote-mcp-github-oauth
MIT copyright (c) 2025 Cloudflare, Inc. Notice included below.

## License/NOTICE

MIT License
Copyright (c) 2025 Cloudflare, Inc.
Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included
in all copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

## Cloudflare Git-build settings (avoid accidentally deploying CACE)

**Diagnosed October 9:** The successful deployment to
`https://cace-app.morganaspiro.workers.dev` showed `pip install .`,
`Framework: Static`, `Output Directory: web` and only three static files.
That is the **CACE app**, not the Fjord MCP connector. Preserve it and
create a **new Worker**.

For **Workers & Pages → Create application → Import a repository**:

| Setting | Exact value |
| --- | --- |
| Worker name | `fjord-commons-mcp` (not `cace-app`) |
| Git provider | GitHub |
| Repository | `Mannyspiro/expert-robot` (NOT `morganaspim/Cace-app`) |
| Branch containing connector | `research/evidence-conservation-gates-20261009` |
| Root directory | `integrations/fjord-cloudflare-mcp` |
| Framework | Worker / none (do not select Static site or Python) |
| Build command | `npm install && npm run check && npm test` |
| Deploy command | `npx wrangler deploy` |
| Expected entrypoint | `src/index.ts` via the committed `wrangler.jsonc` |
| Expected Worker endpoint after authorization | `https://fjord-commons-mcp.<assigned-subdomain>.workers.dev/mcp` |

Do **not** trigger the final deploy before:
- Creating the Cloudflare **free** `OAUTH_KV` namespace and replacing the
  literal `REPLACE_WITH_CLOUDFLARE_FREE_KV_ID` placeholder in the branch
  configuration, with independent review.
- Configuring your **new** Forgejo OAuth application callback and the three
  Cloudflare runtime secrets, without pasting them into source or chat.
- Confirming any type-check or test failures are repaired. The connector has
  not been end-to-end validated on the deployment platform yet.

Cloudflare Git integration uses the root directory to find each service's
Wrangler configuration and execute its build/deploy commands. Workers' names
must match their Wrangler `name`. The Cloudflare build logs will change from
`pip install .` + `Framework: Static` to `npm install`, type checking, and a
Worker bundle. See:
https://developers.cloudflare.com/workers/ci-cd/builds/configuration/
https://developers.cloudflare.com/workers/ci-cd/builds/advanced-setups/

