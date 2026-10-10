# Expert Robot — Cloudflare Free observer (toy-only)

This is a **separate Cloudflare Worker**. Do not replace or rename the existing
`cace-app` website Worker. No Fjord, Forgejo, deploy keys, paid products,
external API, secret, or shell access are required for this program.

## What it really does

- A fixed daily 16:23 UTC Cron Trigger computes four small **synthetic**
  reaction-conservation checks using BigInt exact rational arithmetic.
  Expected left nullities: `[2,1,2,1]`; all residuals: exactly `0`.
  Mutations check a missing-reactant mass defect of `1/3` and invalid mixed units.
- Stores one immutable receipt **per UTC day** in a single SQLite-backed
  Cloudflare Durable Object, which is supported on Workers Free.
- `GET /health` reports the program's role; `GET /v1/receipts/latest` returns
  the latest **public synthetic** receipt. No HTTP route can trigger an
  experiment, modify receipts or update any repository.
- An outage, duplicate date or inconsistent receipt fails closed.
- Declares `lean_kernel_checked=false`, `cace_certificate=false`,
  `production_promotion_authorized=false`, `authority_expanded=false`.
  Does NOT run the Python experiment suite, CACE solver, Lean, models, RSI,
  code changes, or independent validation of mathematical claims.
- Does NOT claim the receipt is tied to the Git source SHA. This is a
  fixed-JavaScript parity/regression observation, **not** independent proof.

## Validation completed before staging

`npm test` on local Node 22 ran five checks successfully:
determinism, exact numerical results, read-only routes, duplicate run,
digest tamper detection, immutable-day conflicts, schedule rejection.

`npm install` for Wrangler timed out in the author's environment, so **a live
Cloudflare runtime build or deployment is not yet verified**. These Node tests
mock SQLite and Durable Objects; run `wrangler dev --test-scheduled` after
dependency installation, and inspect the first daily receipt in production.
No service should be considered operational solely from this source.

## Free limits and stop conditions

Cloudflare Workers Free currently documents 10 ms CPU per HTTP/Cron
invocation, 100,000 requests/day and 5 Cron Triggers/account. SQLite Durable
Objects on the Free tier have hard limits; operations fail rather than
automatically charging paid overages. Verify your account is Workers **Free**;
do not upgrade or enable paid products. CPU time must be assessed in
Cloudflare, not assumed from local benchmarks.

Sources:
https://developers.cloudflare.com/workers/platform/limits/
https://developers.cloudflare.com/durable-objects/platform/pricing/
https://developers.cloudflare.com/workers/ci-cd/builds/configuration/

## Mobile deployment (manual approval required)

The deploy-ready branch is `deploy/cloudflare-research-observer` in
`Mannyspiro/expert-robot`. It has this Worker at the repository **root**,
so Cloudflare doesn't need a root-directory override.

1. In Cloudflare dashboard: Workers & Pages > Create application >
   Import a repository > GitHub > `Mannyspiro/expert-robot`.
2. Name the NEW Worker `expert-robot-observer` (keep `cace-app` untouched).
   Select production branch `deploy/cloudflare-research-observer`.
3. Set build command to `npm install && npm test`; deploy command
   `npx wrangler deploy`. Cloudflare's free tier only.
4. Review the pending deployment; ensure the runtime is Workers rather than
   a static `web` asset build. Approve only if it shows the correct
   `wrangler.jsonc`, `src/worker.mjs` and SQLite Durable Object migration.
5. After deployment check `https://expert-robot-observer.<your-workers-subdomain>.workers.dev/health`
   (the subdomain must be confirmed in dashboard, not guessed). After the
   scheduled UTC run, inspect `/v1/receipts/latest`. A 404 before the
   first completed scheduled run is expected.

Source editing lives under `integrations/cloudflare-observer/` in the
Expert Robot research branch. Keep production deployment changes reviewed;
this branch is NOT on the mainline and does not auto-promote science or code.
