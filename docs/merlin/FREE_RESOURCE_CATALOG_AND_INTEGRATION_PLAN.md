# Merlin zero-configuration resource policy

Reviewed: 2026-11-06.

## Hard constraint

The production build must not require the project owner to create external accounts, obtain API keys, configure tokens, register domains, provision third-party databases, or manually activate free-tier services. A service that requires any of those steps is not an active dependency. Do not describe it as integrated or production-ready.

Merlin must remain useful with its own application, local durable stores, and installed open-source toolchains. Public unauthenticated APIs may be used through bounded adapters, but they are optional research inputs and never execution authorities or proof authorities.

## Active zero-configuration resources

| Resource | Merlin use | Operating rule |
|---|---|---|
| Crossref REST API | DOI metadata and scholarly discovery | Fixed public endpoint; bounded requests; cache; preserve DOI and response digest; identify results as unverified documents |
| arXiv API | Preprint discovery | Fixed public endpoint; bounded requests; cache; preserve arXiv identifier and response digest; identify results as unverified documents |
| Python standard library | API, parsing, persistence, hashing, tests | No external runtime service or account |
| SQLite | Local event, learner, registry and outbox persistence | Durable local state; explicit transactions, backup/restore tests and resource closure |
| Lean 4 / mathlib | Formal proof and reproducible math verification | Use an already available pinned toolchain; never report a proof without compiler output and source/toolchain binding |
| FreeCAD | CAD import and engineering model workflows | Use only where installed on a qualified local/Avrea/OCI runner; absence is reported as unavailable |
| ngspice | Circuit simulation | Use only where installed on a qualified runner; record exact binary version and input/output digests |
| Existing Avrea and OCI runners | Isolated execution | No runner is considered qualified until actual identity, labels, capacity, logs and CACE-verifiable evidence are observed |

## Not active dependencies

Gemini, Groq, PostHog, Neon, Supabase, Upstash, Resend, hosted quantum hardware, and any service requiring credentials or a project setup are not part of the active production path. Do not add configuration instructions for them to Merlin's setup or require them in CI. They can be reconsidered only if the user explicitly changes the zero-configuration constraint.

No Cloudflare service is included.

## Public literature adapter

The current implementation is `python/merlin/public_literature.py`, exposed at `GET /api/research/literature?q=...&source=all|crossref|arxiv&limit=10`.

The adapter:
- uses fixed public Crossref and arXiv hosts;
- needs no API key or user configuration;
- bounds query size, result count, response size and network timeout;
- caches results and rate-limits calls;
- preserves DOI/arXiv identifiers, retrieval time and raw response SHA-256;
- records source failures without fabricating results;
- marks documents as `OBSERVED_DOCUMENT` and claims as `NOT_VERIFIED`.

A paper record is not a verified scientific claim. Formal, numerical, engineering and CACE verification remain separate evidence stages.

## Production acceptance rule

A capability is not production-ready until its actual implementation is exercised by automated tests, the exact commit is recorded, logs and machine-readable results are retained, failures are investigated, and any required independent CACE receipt is verified. Pending, cancelled, skipped, unavailable and unqualified states must remain visible rather than being presented as success.
