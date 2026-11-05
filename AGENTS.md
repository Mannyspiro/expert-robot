# Repository agent instructions

Before working on Merlin, Hermes, Avrea or CACE, read [docs/AI_RUNNER_AND_BRIDGE_OPERATIONS.md](docs/AI_RUNNER_AND_BRIDGE_OPERATIONS.md), then [docs/MERLIN_AVREA_HERMES_ROUTING.md](docs/MERLIN_AVREA_HERMES_ROUTING.md) and [docs/cace-bidirectional-bridge.md](docs/cace-bidirectional-bridge.md). Fetch live workflows and exact-run evidence; do not rely on historical chat context.

- Capability grows; authority never expands.
- Do not claim runner dispatch, Lean compilation, tests or CACE verification without evidence.
- Never commit credentials, private keys or certificates.
- The CACE-app SSH key is repository transport access, not verifier authentication.
- Keep Lean compilation separate from CACE proof verification.
- Keep training and held-out corpora disjoint and versioned.
- Do not merge or deploy without explicit approval.

- If independent CACE credentials are unavailable, keep research and artifact capture running with `artifact_verifier=None`; surface `blocked_missing_credentials` and never claim verification or promotion.
- Never create placeholder secrets to satisfy GitHub's non-empty secret form.
