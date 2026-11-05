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

## Exact source binding and CACE artifact verification

A task may optionally bind to an exact `source_repository` (`owner/name`) and lowercase 40-character `source_commit_sha`. The two fields must be supplied together. They are included in the task digest and rendered prompt text; the prompt hash therefore binds the stated source revision.

A worker result must echo the same repository and commit. Output artifacts must include a SHA-256 digest and, when independent CACE verification is requested, a matching descriptor containing logical path, artifact kind and schema.

`PromptCaceEvidenceBridge` submits each declared artifact through the existing `CaceVerificationAdapter.verify_artifact` boundary. That adapter first re-hashes bytes from Merlin's canonical artifact registry, then validates CACE's receipt binding to repository, exact commit, artifact digest, kind, schema and logical path. The bridge accepts only the versioned CACE artifact-verification result and keeps `promotion_authority=false` and `mathematical_proof=false`.

A CACE artifact-verification PASS means the declared artifact schema/content and provenance checks passed under the configured independent verifier. It is not a Lean theorem proof, not a scientific truth claim, and not production qualification. Missing CACE transport, missing artifact bytes, mismatched hashes or incomplete descriptors must fail closed.

**Authentication gap:** the current `CaceVerificationAdapter` v1 receipt contract validates a canonical `receipt_sha256` and a distinct `verifier_id`, but does not yet verify an Ed25519 signature against a pinned/revocable trusted signer key. A digest is tamper detection, not signer authentication. Therefore this bridge is an integration candidate, not an authenticated production attestation path. Before production, add a signed receipt profile binding `key_id`, verifier identity, repository/commit, artifact digest/kind/schema/path, producer and verifier tool versions, policy digest, verification status and explicit nonclaims; validate key trust, revocation and signature before accepting `verified`.


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


## Hermes engineered-prompt bridge

`PromptHermesDispatcher` compiles a `PromptTask` and translates it into the existing `merlin-research-task/1` event consumed by `HermesWorker`. It does not create a second worker protocol.

The bridge requires:
- an explicit recipient-to-stage mapping (`hermes.research`, `hermes.numerical_experiment`, `hermes.proof_search`, or `hermes.electrical_analysis`);
- `bounded_execution` scope and a validated operator approval reference;
- an independently validated MCFC lease and the task's resource budget;
- a declared hypothesis ID and lease reference;
- an idempotent outbox key bound to task ID and compiled prompt SHA-256.

The full compiled prompt payload, required outputs, constraints, acceptance criteria, evidence requirements and tool allowlist are embedded in the Hermes task's `experiment_spec`. The task objective is separately bounded to the Hermes worker's 2,000-character envelope limit.

The existing Hermes worker then revalidates approval and lease at execution time, dispatches only to an explicitly injected stage handler, emits telemetry, stores a result receipt and acknowledges the leased event. A result-correlation helper checks task ID, prompt hash, task hash and source repository/commit against the compiled prompt.

**Boundary:** the bridge and worker test establish a local outbox-to-injected-handler round trip. They do not prove that a production Hermes process is deployed, that concrete research/solver handlers are configured, or that a live Avrea/CACE service transport is connected. CACE verification, Lean proof, independent assessment and human approval remain separate gates.
