# Bidirectional CACE ↔ Expert Robot bridge

Two repository-scoped deploy keys are used without sharing their private material between execution domains.

## Forward path

Expert Robot secret → trusted dispatcher → isolated Cace-app bridge branch → free CACE ARM64 runner.

The self-hosted runner has `contents: read`, `persist-credentials: false`, no Expert Robot reverse deploy key, and no merge or promotion authority. It performs bounded static/formal qualification and uploads evidence as an artifact.

## Reverse path

A separate GitHub-hosted Cace-app publisher receives the qualification artifact. Only when `status == pass` may it use the Cace-app secret whose deploy key is scoped to Expert Robot.

Supported reverse-key secret names:

- `EXPERT_ROBOT_SSH_PRIVATE_KEY`
- `EXPERT_ROBOT_DEPLOY_KEY`
- `CACE_TO_EXPERT_ROBOT_SSH_KEY`
- `EXPERT_ROBOT_DEPLOY_PRIVATE_KEY`

The first configured value is used.

The publisher creates only `cace-return/<request-id>` in `Mannyspiro/expert-robot`, containing `.cace-return.json`, bounded qualification evidence, and the original request envelope. It does not merge anything.

## PR creation

Expert Robot's `CACE Return PR` workflow validates pass status, request schema, source SHA, source/base agreement, qualification-only authority, `promotion_authority == false`, and the evidence namespace. It then uses Expert Robot's own scoped `GITHUB_TOKEN` to create a PR.

## Base44

Base44 is treated as a discoverable external integration only. Capability discovery may report tracked Base44 markers, but this bridge does not deploy to Base44, invoke Base44 APIs, change Base44 configuration, or authorize paid resources.

The return path preserves `Capability grows, authority never expands.` Automatic merge and automatic promotion remain forbidden.


## CACE Tool Broker v1

Expert Robot treats CACE as a typed external capability provider, not as a
co-owner of the RSI process. The reviewed allowlist and exact CACE source pin
live in `config/cace_tool_broker.json`.

The current capability pin was obtained by a zero-mutation capability probe:

- CACE repository: `morganaspim/Cace-app`
- CACE commit: `0e7aa229d3bb57174e281b883ee8af5445f15f75`
- probe runner: `avrea-ubuntu-latest-1-vcpu`
- probe cache: disabled
- probe run: `36255325310`
- capability artifact SHA-256:
  `f950035062359cd10a1dbd4ee3a33c0ea7462488bdf1414bb9e392064cb2eb4c`

A broker request must bind the exact Expert Robot source commit, exact CACE
commit, allowlisted capability ID, execution lane, input digest, and a bounded
wall-time/Lean-check budget. A returned result must bind the same identifiers
and provide an evidence digest plus the canonical result digest.

`scripts/validate_cace_tool_result.py` fails closed when any of those bindings
drift. A passing result is evidence only. Capabilities explicitly marked
`can_qualify: false` may contribute empirical evaluation evidence but cannot
be mislabeled formal qualification.

### RSI integration

The intended bounded loop is:

1. Expert Robot creates an immutable generation/candidate record.
2. The planner selects an allowlisted CACE capability.
3. A request is admitted only if it matches the pinned CACE revision and
   per-capability compute budget.
4. CACE executes the bounded check without receiving promotion authority.
5. The returned evidence is hash-bound to the request and validated locally.
6. Valid evidence may be recorded in `GenerationLineageStore` as evaluation
   evidence and used by hidden/ablation evaluation.
7. A successful evaluation still requires the existing external promotion
   boundary before a generation or skill becomes promotable.

This keeps CACE useful to recursive improvement while preserving the invariant
that capability may grow without expanding authority.

### External services

- **Base44** is a non-authoritative observability/index layer. It may mirror
  request IDs, hashes, compute use, and candidate status; it must not hold
  canonical proofs, credentials, or promotion authority.
- **Railway** may later provide a sleeping/event relay for asynchronous jobs,
  but it is not a verifier or qualification authority.
- **Vercel** may host a read-only control/observability UI when a project is
  connected; it is not an authority boundary.
- **Avrea** is used for general C++/benchmark qualification only when cheaper
  static/CACE checks justify escalation. Capability discovery uses the smallest
  available 1-vCPU lane and does not use cache.


### Deterministic capability routing

`scripts/plan_cace_tool_requests.py` converts a candidate's changed paths into
a bounded verifier plan without model calls or network access:

- one Lean-only change → exact-pin CACE Lean preflight;
- multiple/mixed formal changes → bounded CACE batch Lean preflight;
- Python changes → non-authoritative CACE regression checks;
- collaboration contract changes → CACE collaboration validation;
- C++/model/runtime changes → Avrea remains required because CACE OCI is not
  treated as a C++ build lane;
- docs-only or unrelated configuration changes → no CACE request is created.

Mixed formal/C++ candidates may use CACE for the formal evidence first while
still requiring Avrea repository qualification afterward. The planner never
dispatches automatically and every generated CACE request is validatable by
the broker contract.


### Required verification gates

When the deterministic planner selects a CACE capability marked
`can_qualify: true`, the admitted request is recorded in generation lineage as
a required gate **before** external execution begins. The initial gate state is
failing and is hash-bound to the admitted request.

This gives promotion a fail-closed lifecycle:

1. required request admitted → gate blocks promotion;
2. no result / timeout → gate remains blocking;
3. failed broker-validated result → gate remains blocking;
4. passing broker-validated result → latest gate state passes;
5. later failed recheck → latest gate state blocks again.

CACE gate evidence never sets `recommend_keep`, efficiency, diversity, or
external approval. Those remain independent hidden/ablation and authority
boundaries.
