# Graft scripted tool-acquisition evaluation — Merlin checkpoint

**Status:** Verified upstream simulated integration only; **not** approved for Merlin tool authority.

- Candidate: [getmodern-ai/graft](https://github.com/getmodern-ai/graft), Apache-2.0, exactly commit `c77155dcac2d7988fa27268c5ea78c23b651d5ab`
- Merlin review: [draft PR #209](https://github.com/Mannyspiro/expert-robot/pull/209), based on Merlin optional component PR #207
- Evidence: [GitHub Actions 45098211811](https://github.com/Mannyspiro/expert-robot/actions/runs/45098211811), **success**
- Download [nonsecret scorecard artifact 14784008613](https://github.com/Mannyspiro/expert-robot/actions/runs/45098211811/artifacts/14784008613), expires December 7, 2026

## Measured results

GitHub Actions installed the upstream dependency lockfile with Node.js 24 and pnpm 10.6.1, ran its real scripted acquisition harness with canned model replies and four fake vendors, and independently checked the scorecard for `OVERALL 4/4 scenario(s) passed whole`. The vendor fixtures exercised: read-only orders, create an order after approval, SDK proxy handling, and a two-stage 3 MiB file transfer using blob refs. The upstream scorer printed passes for `credential_never_recorded` and `publish_before_first_write` for each applicable scenario. The harness's unit tests ran successfully (2 passing test files). This is a **bounded reproducibility result on synthetic vendors**, not a guarantee for arbitrary remote APIs.

## What was not executed

No real model provider, private account, real vendor, production credential, autonomous tool promotion, Merlin plugin/tool deployment or real vendor write. Graft's working set is not Merlin's canonical policy/registry, and a Graft success does not override the host's explicit approvals.

## Required integration gates

1. Use a local fake API provider under independently configured permissions and reject writes until explicit approval. Collect the actual HTTP event stream and credential redaction evidence, then compare with the upstream scorecard.
2. Bind any proposed tool source and schema to an immutable hash and independently reviewed provenance; run it under the OpenSandbox execution boundary only after native isolation qualification.
3. Keep tool registry, artifact receipts and ownership with Merlin's existing canonical ArtifactRef and approval gate; no automatic Graft `promote` action.
4. Test recovery and rollback for failed tool generation, partial vendor responses, held approvals and interrupted tasks. Release only after explicit review.

## Skeptical-scientist decision

Hypothesis: on-demand connectors can reduce repetitive integration work without expanding authority. Alternative: generated tools or replayed fixtures hide real API/credential risk. Observable falsifier: a tool writes without a person's approval, leaks a credential, cannot replay its source/receipt, or bypasses sandbox networking. N-ality: distinguish tool correctness, authority, source integrity, cost and persistence. Simplex/continuum deferred pending live measurements. Fuzzy authorization not applicable.
