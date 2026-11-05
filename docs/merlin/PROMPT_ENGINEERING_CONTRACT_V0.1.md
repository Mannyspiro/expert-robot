# Merlin Engineered Prompt Contract v0.1

**Status:** implementation candidate; draft PR only  
**Owner:** Merlin / Expert Robot  
**Module:** `python/merlin/prompt_contract.py`

## Purpose

Merlin must be able to turn a research, engineering, verification or operations objective into a structured prompt that can be addressed to a named subsystem or used by Merlin itself. A prompt is a versioned task artifact, not an execution grant.

The first implementation provides deterministic compilation and durable outbox publication. It does not yet claim that Hermes, CACE, MCFC, Avrea, CAD tools or external services consume the new prompt topic. Each recipient needs a separately tested adapter.

## Contract

A `PromptTask` contains:

- stable task ID and recipient subsystem identifier;
- objective and context;
- explicit input references;
- required outputs and acceptance criteria;
- constraints and evidence requirements;
- tool allowlist and resource limits;
- authority scope and optional approval reference.

Compilation produces `merlin-engineered-prompt/1` with the rendered prompt, task SHA-256 and prompt SHA-256. Canonical JSON and deterministic section ordering make identical task specifications produce identical hashes.

## Prompt boundary

The generated prompt explicitly states that supplied context, repository contents, external documents and tool output are data, not instructions. They cannot change the task, recipient, tool allowlist, resource limits or authority scope.

The worker must return a structured status, outputs, tests, evidence references, artifact hashes, limitations and any required next approval. Missing evidence must be reported as missing; it must never be invented.

## Publication and routing

`PromptOutboxPublisher` writes to `merlin.prompt.<recipient>` only after:
1. the recipient validator confirms the subsystem is registered and enabled;
2. for `bounded_execution`, an independent approval validator confirms the approval reference;
3. the durable outbox accepts the idempotent task/hash key.

Publication is at-least-once via the existing outbox. Consumers must deduplicate by event ID and task/hash identity, claim work with a lease, return a correlated result, and acknowledge only after durable result persistence.

## Worker result and acknowledgement contract

The result envelope is `merlin-engineered-result/1`. It binds the task ID, recipient, prompt SHA-256, task SHA-256 and worker identity to a bounded result status.

Required return data includes:
- status: `completed`, `partial` or `blocked`;
- outputs and limitations;
- tests run and one explicit result per test;
- evidence references and artifact SHA-256 values;
- tool names and exact versions;
- any next required approval.

`PromptResultReceiver` checks the event topic, active lease owner/token, prompt schema, prompt text hash, task-hash binding and result correlation before acknowledging the outbox event. The result is stored on the acknowledged event with a canonical result SHA-256. A repeated identical return is idempotent. A malformed or mismatched result is quarantined; a caller without the active lease cannot acknowledge or quarantine the event.

This implements the durable local result-return boundary. It does not yet prove that a live Hermes process consumes the topic or that a remote worker can reach this receiver. The next adapter must expose this boundary through an authenticated transport and be tested end to end.

## Authority model

- `draft_only` is the default.
- `bounded_execution` requires an approval reference and independent validation.
- No prompt can grant new tool permissions, repository write access, deployment rights, merge rights, verification authority or promotion authority.
- Merlin may compile and inspect prompts without dispatching them.
- A prompt response is an untrusted candidate result until its artifacts are checked and CACE or another independent verifier accepts the relevant claims.

## Next integration gates

1. Add a Hermes consumer for `merlin.prompt.<recipient>` with event-ID deduplication, lease handling and result correlation.
2. Add a result envelope binding task ID, prompt hash, input hashes, worker identity, tool versions, output hashes and test logs.
3. Add a CACE receipt verifier that rejects mismatched prompt/source/artifact hashes and keeps assumptions explicit.
4. Add read-only prompt preview and approval UI to Merlin's dashboard.
5. Add end-to-end tests for compile -> publish -> claim -> execute -> result -> verify -> acknowledge, including retry, timeout, duplicate delivery and tampering cases.

## Validation

The PR adds deterministic compilation, hash-binding, recipient validation, approval gating and idempotent outbox tests. CI must publish the test log and machine-readable test result artifact even when a test fails. No live worker execution, CACE qualification or production deployment is claimed by this change.
