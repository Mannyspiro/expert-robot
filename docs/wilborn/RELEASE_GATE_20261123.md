# Wilborn MVP release gate (2026-11-23)

Current state: draft PR; code committed; CI results pending. No production launch, no real client data.

## Required independent evidence
- Run Python 3.11 workflow tests and preserve exact commit and CI run ID.
- Verify persistence after process restart, tamper detection, denial of sensitive agent actions.
- Check for exposed credentials without printing values; revoke/rotate only using approved provider-side credential broker.
- Threat model: unauthenticated API, client-data access, malicious instructions, secret disclosure, workflow injection and unauthorized agent actions.
- Require human approval before deploying, sending messages, signing documents or accessing customer data.

## Business architecture
ChatGPT: conversational entry point via future authenticated connector.
Titan: business reviewer and operating-process evaluator (planned, not connected).
Merlin: code/research worker, no direct secrets or PII.
Artex: independent security reviewer (planned, not connected).
Protected service: authoritative records, authentication, authorization, audit and approved actions.

## Do not mistake
A source policy for runtime enforcement, unit tests for penetration testing, hash chaining for encryption, or a CI green result for production readiness.
