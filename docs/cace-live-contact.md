# CACE live contact — 2026-09-27

## Observed, not inferred

- Both configured loopback endpoints refused connections in the ChatGPT execution workspace. This says nothing about loopback services on the CACE runner.
- Railway project KSEE FINAL reports Cace-app deployment `464439aa-1dae-4b20-9bfa-80541b9199dc` as FAILED. Its service configuration has no start command and no declared runtime variables. It is not evidence of a running local model.
- Expert Robot bridge run `36293296633` successfully prepared its deploy key and pushed a request to Cace-app. It failed at `Await external free-runner evidence` with a timeout after approximately 23 minutes. This is a missing-result observation, not proof that the CACE runner is offline. Queue, execution and publication remain unresolved.
- Direct Cace-app GitHub access through the connected API returns 404. A repository deploy key is usable inside its configured trusted workflow, not a shell credential for the runtime host. No secret values were requested or printed.

## Same-host check

Run the following on the host where the pinned CACE and llama-server processes are actually installed:

```sh
python3 scripts/probe_cace_llm.py --infer --timeout 10
```

The diagnostic separately checks CACE health, the expected model ID and one response capped at 32 output tokens. No redirects, proxies, downloads, process launches, tool calls, or configuration changes. The timeout is a per-operation socket timeout; use an outer job timeout for a hard overall bound. Exit 0 means the requested checks passed, not that the model bytes or reasoning correctness are proven. JSON explicitly labels host scope, untrusted text, no byte attestation, no formal verification and no promotion authority.

## Next iteration, ranked

1. Recover visibility of the existing CACE bridge job and result publication before dispatching another polling run. Inspect its queue/job status on Cace-app through an authorized account or trusted bridge; direct API access here is unavailable.
2. On the actual runtime host, run this diagnostic. If unavailable there too, establish the installed model and runtime paths, validate independently expected hashes and launch the existing pinned local runtime. Do not use the hashes of arbitrary files as provenance.
3. After one live response, run the existing headless e2e smoke and one bounded typed CACE experiment. Keep inference and verifier evidence separate.
4. Only then measure a candidate against a fresh hidden baseline and consider the next generation.

Local diagnostic tests use mocked endpoint responses and are not live model evidence. The checked configuration came from Expert Robot commit `e2971ce36663e2ed8f70256c77c8cb5280a82cdf`; that is an inspected source reference, not an attestation of the running services.

No Avrea job, Railway deployment or paid service was launched for this diagnostic. User-reported Avrea balance remains 1,000 September credit minutes; it was not refreshed from provider billing.
