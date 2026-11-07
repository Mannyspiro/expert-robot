# Merlin free-resource catalog and integration plan

Reviewed: 2026-11-06. Prices and quotas change; re-check provider dashboards before launch. Free quotas are capacity ceilings, not production SLAs.

## Recommended stack

| Merlin subsystem | Free service / project | Free allowance observed | Integration decision |
|---|---|---|---|
| Primary hosted LLM | Google Gemini Developer API | Free usage exists for selected models; per-model rate limits are visible in AI Studio and can change | **Adapter profile added**. Configure a free-eligible model, API key and qualification receipt before enabling |
| Secondary hosted LLM | Groq API | Free developer tier with model-specific RPM/RPD/TPM/TPD limits | **Adapter profile added**. Configure a free-eligible model and qualification receipt before enabling |
| Canonical Postgres | Neon Free | Up to 100 projects; per project 100 CU-hours, 1 GB storage and 5 GB public transfer/month | Candidate for development/early alpha persistence. Not a substitute for backups, a production SLA or the existing artifact registry |
| Auth and small object storage | Supabase Free | Two free projects; 500 MB database/project, 1 GB storage, 5 GB egress, 50,000 MAU and 500,000 Edge Function invocations | Optional identity/storage service. Do not duplicate the current OIDC identity authority without a migration plan |
| Product analytics, error and AI observability | PostHog Free | 1M analytics events/month, 100K exceptions/month, 100K AI observability events/month, 10 GB logs/month, 5K session recordings/month | Recommended for aggregate product/system measurements. Do not send raw prompts, private files, credentials or personal learning records |
| Transactional email | Resend Free | 3,000 emails/month, 100/day, 3 domains | Optional approval, account and job notifications; requires a verified sending domain |
| Ephemeral cache / rate limits | Upstash Redis Free | Published current comparison reports 250 MB and 500,000 commands/month; verify the live account quota | Optional cache only. Hermes durable outbox and canonical database remain authoritative |
| Local engineering / simulation | FreeCAD, ngspice, Lean 4, Python scientific stack | Open-source software; local compute is the constraint | Keep execution on qualified Avrea/OCI or local runners; retain exact toolchain and output receipts |
| Literature / research data | arXiv API, Crossref REST API, OpenAlex API, PubMed E-utilities | Public research APIs with provider-specific rate limits and attribution requirements | Add rate-limited source adapters; preserve DOI/arXiv IDs, retrieval timestamps, source hashes and licensing |
| Quantum experiments | IBM Quantum Open Plan / Qiskit | IBM documents a free Open Plan; hardware availability and queue access are account- and time-dependent | Research adapter only. Simulator first; hardware execution is a separately qualified, non-deterministic external job |

### Explicit exclusions and cautions

- Cloudflare is intentionally excluded because the project owner previously disabled/removed it. Its free Workers/Workers AI quota is not part of this integration plan.
- Vercel Hobby is free for personal, non-commercial use; do not use it as Merlin's commercial production host. Keep Vercel as an optional preview/development target only if the use complies with its current plan terms.
- Free serverless/database tiers can pause, throttle, queue, or stop at quota. Do not use them as the only durable queue, proof authority, or artifact source of truth.
- Never assume a provider's free quota will be available to all end users, in all countries, or for commercial use. Verify terms, privacy, retention, and rate limits before exposing it to users.
- Gemini unpaid-service data may be used to improve Google products. Do not send confidential or sensitive user material to a free-tier model. Use redaction and an explicit user/provider policy gate.
- Do not store user prompts or raw learner content in product analytics. Merlin's canonical event store remains the system of record; PostHog receives minimized, pseudonymous operational metadata only.

## Implemented in this change

The existing Merlin cloud model path already supports an OpenAI-compatible HTTPS endpoint and bearer key. It now has two built-in, host-pinned profiles:

\`\`\`bash
# Gemini Developer API profile
MERLIN_REMOTE_PROVIDER=gemini
MERLIN_REMOTE_API_KEY=<secret-from-Google-AI-Studio>
MERLIN_REMOTE_MODEL_NAME=<currently-free-model-id>
MERLIN_REMOTE_MODEL_QUALIFIED=0
\`\`\`

\`\`\`bash
# Groq profile (alternative; select one provider per process)
MERLIN_REMOTE_PROVIDER=groq
MERLIN_REMOTE_API_KEY=<secret-from-Groq-console>
MERLIN_REMOTE_MODEL_NAME=<currently-free-model-id>
MERLIN_REMOTE_MODEL_QUALIFIED=0
\`\`\`

The endpoint and allowed host are pinned by the profile. A caller cannot override a Gemini profile to an arbitrary host. For a custom OpenAI-compatible endpoint, keep \`MERLIN_REMOTE_PROVIDER=custom\` and supply both \`MERLIN_REMOTE_MODEL_URL\` and \`MERLIN_REMOTE_ALLOWED_HOSTS\`. Credentials must be injected by a secret manager and must never be committed.

The model remains unavailable until its model ID, endpoint, rate-limit behavior, privacy review and held-out task results have been recorded in a qualification receipt. The environment flag is a deployment gate, not evidence that a model passed qualification. There is no automatic fallback between providers: a provider switch is explicit and logged.

PostHog export is now implemented as an optional background service. It reads only Merlin's stored event metadata, advances a durable export cursor only after a successful batch response, uses stable insert IDs for retries, and exposes health at `/api/runtime/analytics`. It is disabled unless a project token is configured.

```bash
MERLIN_POSTHOG_PROJECT_TOKEN=<project-write-token>
MERLIN_POSTHOG_REGION=us
MERLIN_INSTANCE_ID=<non-identifying-instance-label>
MERLIN_POSTHOG_POLL_SECONDS=5
MERLIN_POSTHOG_BATCH_SIZE=100
```

Only the US and EU public capture hosts are supported. The exporter does not transmit request bodies, prompts, learner answers, raw artifact content, request hashes, user IDs or credentials. It exports allowlisted event kind and operational summary fields only. A token is not currently configured in the deployment, so the adapter is implemented and testable but live PostHog delivery is not yet active.

## Integration sequence (ranked)

1. **Provider qualification, no new infrastructure.** Configure one free provider at a time in a non-production environment. Run held-out tasks for instruction following, structured JSON, code patch quality, multilingual handling, latency, token limits, prompt injection resistance and refusal behavior. Record provider/model/revision, exact limits, test set digest, score, latency distribution and privacy approval. Keep \`MERLIN_REMOTE_MODEL_QUALIFIED=0\` until independently reviewed.
2. **PostHog operational telemetry.** Create one project, use the US or EU public capture endpoint, and send only pseudonymous event metadata, aggregate latency, provider/model identifiers, stage outcomes, retry counts and error classes. Keep canonical event/outbox data in Merlin. Set billing limits and disable session replay for sensitive workflows.
3. **Neon persistence pilot.** Implement a Postgres repository interface behind the existing registry/graph APIs; dual-write in a test environment, compare canonical hashes and replay results, then cut over only after backup/restore and concurrency tests. Do not split authority across SQLite and Postgres.
4. **Supabase Auth or current OIDC.** Retain the current OIDC boundary unless a concrete user-management need justifies a migration. If Supabase is chosen, map stable subject/tenant IDs and verify issuer, audience, JWKS rotation, tenant isolation and account deletion behavior.
5. **Resend notifications.** Route approval requests and worker completion notices through the durable outbox; idempotency keys and delivery receipts must be retained. Email never approves an execution by itself.
6. **Upstash cache only if measured.** Add it only when metrics show a need for shared ephemeral caching/rate limiting. Do not migrate Hermes leases or durable tasks to Redis.
7. **Research and quantum adapters.** Add source-specific fetchers and IBM Quantum execution as research tools. Their returned outputs are untrusted artifacts until CACE verifies exact inputs, source provenance, tool versions and result digests.

## Acceptance gates

- Free-tier provider is selected explicitly and never silently changes due to a rate limit.
- Credentials are absent from logs, telemetry, repository history and client responses.
- Provider limits and 429/retry-after behavior are measured and enforced.
- The user can opt out of third-party inference; local/no-provider mode remains available.
- Analytics receives no raw conversation, prompt, artifact content, identity attributes or learner assessment answers.
- Canonical registry, outbox, artifact bytes and CACE receipts remain exportable and independently verifiable.
- Every external job records provider, region, model/tool revision, request digest, response digest, resource budget, timestamps, outcome and failure logs.
- Quota exhaustion degrades to explicit \`unavailable\` or \`unqualified\`, never fabricated success or silent paid overage.
