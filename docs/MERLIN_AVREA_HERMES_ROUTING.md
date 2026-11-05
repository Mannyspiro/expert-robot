# Merlin / Hermes / Avrea quick reference

Canonical repository entry point for future handoffs and agent prompts.

## Avrea runner bridge
- External bridge: .github/workflows/external-free-runner-bridge.yml
- Math benchmark: .github/workflows/math-benchmark.yml
- RSI qualification: .github/workflows/production-rsi-qualification.yml and .github/workflows/rsi-candidate-qualification.yml
- CACE return smoke test: tests/cace_return_bridge_smoke.py
- Compute policy: config/compute_policy.json

The existing bridge uses the Avrea hosted label avrea-ubuntu-latest-8-vcpu, packages a bounded source snapshot, then targets a separate CACE-app runner labelled self-hosted/cace/oci/aarch64. This is a GitHub Actions runner bridge, not a direct Avrea API client. Its RAILWAY_SSH_PRIVATE_KEY is a CACE-app repository deploy key, not CACE verifier authentication. The Avrea CA certificate mount is TLS trust, not an API credential.

The current bridge push trigger names feat/reuse-refactored-fishstick; for other branches use workflow_dispatch after checking secrets and branch selection. Do not dispatch qualification workloads without explicit approval.

## Independent CACE endpoint secrets
Use a protected GitHub Actions Environment named cace-independent-verifier. Configure CACE_VERIFY_URL and CACE_VERIFY_TOKEN as environment secrets; optionally CACE_CLIENT_CERT_PEM and CACE_CLIENT_KEY_PEM for mutual TLS. Restrict deployment branches and require reviewers. Prefer GitHub OIDC-issued short-lived credentials if the verifier supports federation. Never commit or print values. The connected GitHub integration does not expose secret write/read operations here, so the secret values must be configured in GitHub Settings → Environments by an authorized maintainer.

The HTTP transport must POST the adapter request JSON over HTTPS, apply time/response-size limits, and return the exact receipt schema validated in python/merlin/cace_adapter.py. Independent identity, source commit and artifact digest must be verified by the remote verifier, not inferred from a separate URL.

## Hermes claim routing
python/merlin/hermes_claim_routing.py implements deterministic fail-closed routing. Complete grounded claims may go to Lean only when the exact formal statement is present in the supplied Lean source and assumptions, falsifiability and source IDs are present. Ambiguous claims stay research-only; malformed claims are rejected; previously rejected claims are quarantined. sorry/admit/unreviewed axioms are not dispatched.

Lean compilation is compiled_unverified, not proof verification. Independent CACE verification is separate and only an exact-input CACE receipt can establish independent verification.

## Training and evaluation
Labelled corpora: tests/fixtures/hermes-routing-train.json and tests/fixtures/hermes-routing-heldout.json. Run PYTHONPATH=python pytest -q tests/test_hermes_claim_routing.py. Metrics keep false eligibility, missed eligibility, unnecessary Lean dispatch, compilation failure and CACE rejection separate. Held-out IDs are checked for overlap. Never tune on held-out outcomes; freeze a replacement held-out set before moving old examples into training. Store policy version, corpus hashes, Lean toolchain and CACE receipt IDs per evaluation.

## Discovery for all project chats
Read this page at the start of Merlin/Hermes/Avrea/CACE work. AGENTS.md points agents here. robot.txt is not a standard coding-agent instruction file.

## When CACE credentials are not available

Do not create placeholder secrets such as `pending`, `none`, or `TODO`. GitHub requires non-empty values, but placeholder values do not authenticate a verifier.

Merlin's research, numerical experiment and proof-search stages must remain usable without an independent CACE endpoint. Register the Hermes handlers with `artifact_verifier=None` until a real verifier transport is configured. The stage still stores its exact output in the canonical registry and returns the explicit status `blocked_missing_credentials`; it must not emit a CACE receipt, claim independent verification, or permit promotion. A failed configured verifier is a real verification failure and must not be downgraded to this missing-configuration status.

When an authorized CACE service operator provides the real endpoint and credential, an administrator can add them under GitHub Settings → Secrets and variables → Actions → Environments → `cace-independent-verifier`. Save `CACE_VERIFY_URL` and `CACE_VERIFY_TOKEN` only with values issued by that service. Optional mutual-TLS values must also be issued by the service. Do not paste credentials into chat, commits, issues, PR comments, or logs. If no CACE operator has issued credentials, leave the environment without these secrets; no manual placeholder is needed.
