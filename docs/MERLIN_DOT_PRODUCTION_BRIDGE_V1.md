# Merlin production bridge for dot

Status: source-authored production candidate with local tests. No live dot connection, OAuth issuer, tunnel, OCI service, coder model provider or independent CACE verifier was provisioned by this change.

## Ranked integration order

This ranking is an engineering recommendation based on reuse, usefulness, cost and current access. It is not a claim of a globally optimal architecture.

| Rank | Integration | Why this comes first | Current result |
|---|---|---|---|
| 1 | Dot as the project coordinator over canonical context and checkpoints | Makes existing Merlin work usable across chats without copying whole histories into every prompt | Source-cited retrieval and handoffs already operate over the saved context set |
| 2 | Private authenticated MCP read plane | Gives dot current context and status through a narrow interface | Five read tools, OAuth resource validation, read-only registry, loopback HTTP |
| 3 | Separate request inbox | Lets dot turn user intent into durable bounded work without making it an executor | Two request tools, separate scope, authenticated principal, idempotent persistence |
| 4 | Two coders plus a separate evaluator behind Hermes/MCFC | Makes proposed improvements measurable and resumable | Local workflow tests; live adapters and OS supervisor remain to be configured |
| 5 | Model/inference optimization | Valuable after real work exposes a cost/latency bottleneck | Benchmark compatible local models later; do not install several memory/inference engines at once |

Keep the base model fixed initially. Improve retrieval, procedures, prompts and code candidates against frozen held-out tasks. A successful callback report does not authorize self-modification, deployment, signing or promotion.

## Components and authority

| Component | Allowed operation | Excluded operation |
|---|---|---|
| `dot_ai_os.http_gateway` | Five authenticated context/status reads | Registry writes, job execution, signing, promotion |
| `dot_ai_os.request_gateway` | Submit/read caller-scoped research requests | Caller-selected identity, approval, Hermes enqueue, shell, provider calls |
| `ProductionJobInbox` | Store immutable requests in the existing registry | A competing task/evidence database or dispatcher |
| `DualCoderWorkflow` | Call host-injected coders/evaluator with durable stage identity | Exactly-once guarantees, self-promotion or expanded authority |
| Existing Hermes/MCFC/CACE | Existing operator/lease/execution/evidence gates | Authority inferred from the new inbox or OAuth scope |

The read endpoint requires `merlin:context:read`. The optional request endpoint requires `merlin:research:request` and its own exact resource URL/audience. A read-only token cannot submit a request. Principal identity comes from SDK-verified bearer context, never from model arguments.

Accepted inbox requests remain `pending_operator_review`, `not_dispatched`, `qualification=false` and `promotion_authority=false`. Recording a request is not successful execution.

## Authentication and storage

The installed MCP 1.29 resource-server middleware is reused. It does not issue OAuth tokens. The host supplies a fixed HTTPS issuer, introspection endpoint, resource URL, allowed subjects and any dedicated introspection credentials. Active state, subject, audience/resource, expiry, time bounds and scopes are checked; malformed responses and transport errors deny access. Introspection is bounded, has no redirects and does not inherit proxy environment settings.

The read plane opens SQLite with `mode=ro` and `query_only`, skips constructor migrations, and rejects normal mutation methods. WAL-mode inputs are refused before connection because SQLite can otherwise create side files. Use a consistent host-published read snapshot for a WAL-backed live registry. OS read-only filesystem permissions remain necessary; Python wrappers are not a sandbox.

The request inbox shares the canonical registry and existing cooperative writer lock with the two-coder workflow. Exact repeats return the same request; changed principal/input/budget under the same key conflicts. Bounds include 20 source refs, 128 KiB total source text, a 16 KiB complete request envelope and zero declared paid cost. These fields do not enforce provider billing or subprocess resources; no providers or subprocesses are invoked here.

## Host entry points

With the operator-provisioned configuration and canonical state in place:

```bash
PYTHONPATH=python python -m dot_ai_os.http_gateway --root /var/lib/merlin-dot/state --namespaces rsi merlin xenomaths morgana-cace expert-robot --config /etc/merlin-dot/reader.json
PYTHONPATH=python python -m dot_ai_os.request_gateway --root /var/lib/merlin-dot/state --namespaces rsi merlin xenomaths morgana-cace expert-robot --config /etc/merlin-dot/inbox.json
```

Both listeners bind only to `127.0.0.1`. Use separate ports/resource URLs for the two services. `GatewayConfig` requires `issuer_url`, `introspection_url`, `resource_url` ending in `/mcp`, and an explicit `allowed_subjects` list. The reader default port is 8766; configure another port for the optional request service. Dedicated credentials, when required by the issuer, use `MERLIN_INTROSPECTION_CLIENT_ID` and `MERLIN_INTROSPECTION_CLIENT_SECRET` in a host-owned environment file. Do not use Gmail tokens, GitHub deploy keys, example credentials or values pasted into chat.

The service units under `ops/merlin_dot_mcp/` define separate accounts, filesystem permissions and process/resource restrictions. They are deployment templates, not evidence that these controls ran. Installation must provision the accounts, source checkout, isolated environment, state permissions and real identity configuration; no installation or service enablement is automatic.

Prefer Secure MCP Tunnel from the existing trusted host when available. It can keep the service private without new inbound ports. An authenticated HTTPS gateway is the alternative. No Cloudflare deployment is proposed. ChatGPT custom MCP registration is a separate account/workspace action after a real endpoint or tunnel exists.

References: [OpenAI custom MCP connections](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt), [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), [MCP v1 resource-server authorization](https://py.sdk.modelcontextprotocol.io/v1/authorization/).

## Dot operating loop

1. Read the latest project handoff, capabilities and workflow state.
2. Retrieve task-relevant sources with exact ArtifactRefs and byte locators. Page originals when excerpts are insufficient.
3. Submit one bounded research request through the separately authorized request endpoint, or prepare it for the operator if that endpoint is disabled.
4. The existing operator/Hermes policy decides whether and how to dispatch. MCFC must enforce actual resource limits and worker isolation.
5. Coder A proposes; coder B reviews and proposes an alternative; a separate evaluator measures baseline and candidates on frozen held-out work.
6. Resume stored completed stages, reconcile ambiguous in-flight calls, and append the next handoff. Keep failures and dissent. Retain a candidate only through existing qualification/approval policy.

## Live state and limitations

The dependency remains the exact Expert Robot PR #176 source at `8b83b4dfd639d0abdd3e9b0a7eb695b193d2c7b3`, still an open draft at inspection. Exact-head CI runs 44010725986 and 44010726036 reported success for that base, not for these new changes.

The historical OCI preview workflow depends on Avrea and historical branches/artifacts. It is not reused automatically. Standing context preserves no paid compute and Avrea unavailable until December 1. A failed web retrieval of the recorded preview URL does not establish server health or outage. A current reachable host, real OAuth settings, tunnel/HTTPS connection, deployment approval and actual post-deploy tests remain required.

The new code is carried on a separate review branch based on #176. No merge, workflow dispatch, OCI deployment, secret change, public exposure or CACE promotion is part of this source change. No raw private chat exports or context database are committed.

## Validation

The local selected-dependency suite passes 74 tests: 35 existing context/two-coder/stdio tests, 12 HTTP read/auth tests, 22 inbox tests and 5 real HTTP request/auth integration tests. Tests include 401/403 behavior, resource/subject/expiry checks, namespace and principal separation, malformed introspection, registry integrity/read-only behavior, WAL refusal, idempotency/concurrency, interruption and fixed authority states.

A single local measurement over the 41-record saved context returned five sample queries within a 14,000-byte response budget; median observed time was about 159 ms. This is a warm local observation, not retrieval-quality evidence or a production latency guarantee. No live identity provider, tunnel, dot tool scan, model inference, worker isolation or independent verifier was tested.
