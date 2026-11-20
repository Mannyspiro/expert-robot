# Repository agent instructions

Before working on Merlin, Hermes, Avrea or CACE, read these in order:
1. [Runner and bridge operations](docs/AI_RUNNER_AND_BRIDGE_OPERATIONS.md)
2. [Machine-readable runner catalog](docs/runner-bridge-catalog.json)
3. [Merlin / Hermes / Avrea routing](docs/MERLIN_AVREA_HERMES_ROUTING.md)
4. [Bidirectional CACE bridge](docs/cace-bidirectional-bridge.md)

- Capability grows; authority never expands.
- Fetch live branch heads, workflow files, jobs, logs and artifacts before acting; handoffs and historical runs are not current-state evidence.
- Do not claim runner dispatch, Lean compilation, tests, CACE verification or signer authentication without exact-run evidence.
- Never commit, print, retrieve or request private keys, tokens or certificates.
- The CACE-app SSH key is repository transport access, not verifier authentication.
- Keep Lean compilation separate from CACE proof verification.
- Preserve structured failure results and their provenance.
- Keep training and held-out corpora disjoint and versioned.
- Do not merge, deploy, promote research claims or expand authority without explicit approval.
- If independent CACE credentials are unavailable, keep research and artifact capture running with `artifact_verifier=None`; surface `blocked_missing_credentials` and never claim verification or promotion.
- Never create placeholder secrets to satisfy GitHub's non-empty secret form.
