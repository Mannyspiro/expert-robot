# Merlin Engineered Prompt Pipeline v1

## Purpose

Merlin must be able to transform a research or engineering objective into a reproducible, structured prompt, then either consume it itself or publish it to an explicitly registered subsystem. A prompt is a versioned work artifact. It is not a capability grant, an approval, or an instruction to bypass a subsystem's own admission checks.

## Pipeline

1. **Intent capture** — record objective, target system, task type, context, typed inputs, source references and uncertainty.
2. **Prompt compilation** — deterministically compile instructions, output contract, constraints, acceptance criteria and resource budget.
3. **Qualification** — validate schema, target capability, policy hash, input provenance and prompt digest.
4. **Routing** — choose `self` or an allowlisted subsystem such as Hermes, Lean, CACE, research, numerical experiment or engineering.
5. **Admission** — require explicit approval and an active MCFC lease. Each receiving subsystem independently validates its own permissions and schema.
6. **Execution** — receiver executes only its registered handler; it must not interpret prompt text as authority.
7. **Evidence** — return structured result, logs and immutable artifact references with hashes.
8. **Verification** — CACE independently verifies artifacts/proofs; store receipt and status in canonical registry.
9. **Learning** — compare expected and observed outcomes; revise prompt templates only through versioned, tested changes.

## Contract

The initial implementation is `python/merlin/prompt_engineering.py`:

- `PromptRequest`: typed objective, target, task, context, inputs, instructions, output contract, constraints, acceptance criteria, resource budget and source references.
- `PromptCompiler`: deterministic prompt text and canonical manifest; SHA-256 binds both.
- `PromptDispatchCoordinator`: allowlisted targets, explicit approval, active lease, durable outbox, idempotency and self/subsystem channel.
- `publish_to_hermes`: maps registered prompt task types to the existing `merlin.hermes.task` contract, preserves the compiled prompt and digest in `experiment_spec`, and leaves execution-time approval/lease revalidation to `HermesWorker`.
- Integration test: compiles a prompt, publishes it, lets the real `HermesWorker` claim and acknowledge it using an injected test handler, and verifies the exact prompt digest/text arrived. This is a local contract test, not a live Avrea/OCI run.
- `merlin.prompt.dispatch`: outbox topic for dispatch requests.
- `merlin-engineered-prompt/1` and `merlin-prompt-dispatch/1`: versioned schemas.

## Required next integrations

- Replace the initial target set with the canonical capability registry. A target must resolve to a registered capability, version, input schema, output schema, trust class and policy hash.
- Add adapters: `MerlinSelfAdapter`, `HermesPromptAdapter`, `LeanPromptAdapter`, `CacePromptAdapter`, `AvreaPromptAdapter`, and engineering/research adapters. Adapters must call existing typed interfaces; no duplicate execution engine.
- Add prompt templates for research question, literature review, hypothesis generation, symbolic derivation, Lean proof attempt, numerical experiment, CAD/engineering analysis, ngspice simulation, evidence audit and code repair.
- Add a planner that decomposes a goal into a DAG of prompt tasks with typed dependencies and explicit stop conditions.
- Add receiver-side schema validation and prompt-injection/data-boundary handling. Source documents and retrieved text are untrusted data; they cannot override system/developer policy or the compiled task contract.
- Add feedback metrics: schema validity, completion, reproducibility, evidence quality, verifier outcome, cost and regression rate. Optimize prompts against held-out benchmark tasks, not self-reported quality.
- Show prompt versions, hashes, targets, approvals, leases, results and CACE receipts in the read-only HUD.

## Authority model

Prompt compilation is pure. Publishing requires approval and a valid lease. The prompt cannot authorize access, network calls, code execution, file mutation, merge, deployment, key use or canonical promotion. Receiving systems must enforce their own capability and resource boundaries. Failed or inconclusive verification remains failed or inconclusive; it is never upgraded by prompt text.

**Invariant: capability grows; authority never expands.**
